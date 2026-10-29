import asyncio
import json
import base64
import time
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect

from app.config import settings
from app.services.dialogue_manager import dialogue_manager
from app.services.gnani_stt import gnani_stt
from app.services.gnani_tts import gnani_tts
from app.services.mandi_service import mandi_service
from app.services.arbitrage_engine import arbitrage_engine
from app.services.audio_dsp import acoustic_dsp
from app.services.farmer_db import farmer_db

class VoiceGatewaySession:
    """
    Manages a single full-duplex phone call session over WebSocket.
    Supports real-time barge-in interruption, VAD state coordination,
    STT transcription, reasoning, and Timbre TTS synthesis.
    """
    def __init__(self, websocket: WebSocket, session_id: str):
        self.websocket = websocket
        self.session_id = session_id
        self.phone_number = ""
        self.is_active = True
        self.language = "hi-IN"
        self.api_key: Optional[str] = settings.GNANI_API_KEY
        self.current_tts_task: Optional[asyncio.Task] = None
        self.interrupted_turn_id: Optional[str] = None
        self.active_turn_id: int = 0

    async def send_json(self, payload: Dict[str, Any]):
        if not self.is_active:
            return
        try:
            await self.websocket.send_text(json.dumps(payload))
        except Exception as e:
            print(f"[VoiceGateway:{self.session_id}] Send error: {e}")
            self.is_active = False

    async def handle_start_call(self, data: Dict[str, Any]):
        self.language = data.get("language", "en-US")
        if data.get("phone_number"):
            self.phone_number = data["phone_number"].strip()
        if data.get("api_key"):
            self.api_key = data["api_key"].strip()
            settings.GNANI_API_KEY = self.api_key

        dm_session = dialogue_manager.get_or_create_session(self.session_id)
        dm_session.phone_number = self.phone_number
        farmer = farmer_db.get_farmer(self.phone_number)
        if farmer and farmer.get("language"):
            self.language = farmer["language"]
        dm_session.language = self.language

        greeting_res = farmer_db.get_personalized_greeting(self.phone_number)
        greeting_text = greeting_res["greeting_text"]

        if farmer:
            dm_session.farmer_name = farmer.get("name", "Kisan Bhai")
            dm_session.district = farmer.get("district") or ""
            dm_session.state = farmer.get("state") or ""
            dm_session.location_name = farmer.get("village") or ""
            dm_session.step = "ACTIVE"
        else:
            dm_session.farmer_name = "Kisan Bhai"
            dm_session.district = ""
            dm_session.state = ""
            dm_session.location_name = ""
            dm_session.step = "ACTIVE"
            if self.phone_number:
                try:
                    farmer = farmer_db.update_farmer_profile(
                        phone_number=self.phone_number,
                        name="Kisan Bhai",
                        village="",
                        district="",
                        state="",
                        primary_crops=[]
                    )
                    print(f"[VoiceGateway] Auto-persisted new farmer {self.phone_number} to Supabase")
                except Exception as e:
                    print(f"[VoiceGateway] Farmer auto-persist error: {e}")

        print(f"[VoiceGateway] Call initiated: session={self.session_id}, phone={self.phone_number}, is_new={greeting_res['is_new']}, step={dm_session.step}")
        
        # Send call accepted acknowledgement
        await self.send_json({
            "type": "call_connected",
            "session_id": self.session_id,
            "status": "connected",
            "farmer_phone": self.phone_number,
            "is_new_farmer": greeting_res["is_new"],
            "farmer_profile": farmer,
            "gnani_configured": bool(settings.GNANI_API_KEY),
            "vad_mode": "full_duplex_barge_in",
            "silence_threshold_ms": 1800
        })

        # Synthesize and deliver conversational greeting ONLY if session is fresh (no prior messages)
        if len(dm_session.chat_history) == 0:
            await self._synthesize_and_deliver(greeting_text, step=dm_session.step, extra_data={"is_new": greeting_res["is_new"], "farmer": farmer})

    async def handle_speech_start(self):
        """
        Triggered when Client VAD detects farmer speech onset.
        Barge-in: if AI was speaking or generating speech, immediately cancel!
        """
        self.active_turn_id += 1
        current_turn = self.active_turn_id
        print(f"[VoiceGateway:{self.session_id}] 🎙️ SPEECH ONSET DETECTED (Barge-In triggered, turn={current_turn})")
        
        # Cancel any in-flight TTS synthesis
        if self.current_tts_task and not self.current_tts_task.done():
            self.current_tts_task.cancel()
            print(f"[VoiceGateway:{self.session_id}] Cancelled active TTS synthesis due to farmer interruption")

        # Notify client to immediately halt audio playback and update status
        await self.send_json({
            "type": "barge_in_ack",
            "state": "interrupted",
            "turn_id": current_turn,
            "message": "AI voice halted. Farmer has the floor."
        })

    async def handle_interrupt(self, data: Dict[str, Any]):
        """Explicit barge-in interruption signal from client."""
        await self.handle_speech_start()

    async def handle_speech_end(self, data: Dict[str, Any]):
        """
        Triggered when Client VAD detects 700ms silence after speech.
        Receives recorded WAV audio, transcribes with Gnani Prisma STT,
        reasons through DialogueManager, and synthesizes reply with Gnani Timbre.
        """
        audio_b64 = data.get("audio_data", "")
        self.active_turn_id += 1
        turn_id = self.active_turn_id

        await self.send_json({
            "type": "vad_state",
            "state": "processing",
            "message": "Transcribing with Gnani Prisma STT..."
        })

        transcript = ""
        if audio_b64:
            try:
                audio_bytes = base64.b64decode(audio_b64)
                if len(audio_bytes) > 400:
                    cleaned_audio = acoustic_dsp.clean_audio_for_stt(audio_bytes)
                    transcript = await gnani_stt.transcribe_audio_chunk(
                        cleaned_audio,
                        language=self.language,
                        api_key=self.api_key or settings.GNANI_API_KEY
                    )
            except Exception as e:
                print(f"[VoiceGateway:{self.session_id}] STT decoding error: {e}")

        # If transcription is empty or silent, send clarification prompt
        if not transcript or not transcript.strip():
            # Check if there is manual text fallback in payload
            fallback_text = data.get("text", "").strip()
            if fallback_text:
                transcript = fallback_text
            else:
                await self.send_json({
                    "type": "vad_state",
                    "state": "listening",
                    "message": "Could not detect clear speech. Please speak again or use quick chips."
                })
                return

        print(f"[VoiceGateway:{self.session_id}] Farmer Utterance (Prisma STT): '{transcript}'")
        await self._process_text_utterance(transcript, turn_id, is_stt=True)

    async def handle_user_text(self, data: Dict[str, Any]):
        """Direct text or prompt chip submission over WebSocket."""
        text = data.get("text", "").strip()
        if not text:
            return
        self.active_turn_id += 1
        turn_id = self.active_turn_id
        await self._process_text_utterance(text, turn_id, is_stt=False)

    async def _process_text_utterance(self, text: str, turn_id: int, is_stt: bool = False):
        # 1. Send user transcript to UI only if from voice STT (typed text is rendered optimistically by client)
        if is_stt:
            await self.send_json({
                "type": "transcript",
                "role": "user",
                "text": text,
                "turn_id": turn_id
            })

        await self.send_json({
            "type": "vad_state",
            "state": "reasoning",
            "message": "Evaluating Mandi Arbitrage & eNAM Rules..."
        })

        # 2. Run Dialogue Manager & Arbitrage
        res = await dialogue_manager.process_utterance(self.session_id, text)
        spoken_text = res.get("spoken_text", "")
        step = res.get("step", "")
        extra_data = res.get("data", {})

        # Automatically log every conversation turn into Supabase database
        if self.phone_number:
            try:
                dm_session = dialogue_manager.get_or_create_session(self.session_id)
                farmer_db.log_query(
                    phone_number=self.phone_number,
                    query_type=step or "voice_query",
                    commodity=dm_session.commodity,
                    quantity=f"{dm_session.quantity_quintals} qtl" if dm_session.quantity_quintals else None,
                    utterance=text,
                    response=spoken_text
                )

                # If mandi answered or arbitrage calculated, save to advisory_reports as well
                if step in ["COMMODITY_ANSWERED", "ARBITRAGE_DELIVERED"]:
                    comm = dm_session.commodity or extra_data.get("commodity", "Produce")
                    top_m = extra_data.get("top_mandis", ["APMC Mandi"])[0] if isinstance(extra_data.get("top_mandis"), list) else "APMC Mandi"
                    rate = float(extra_data.get("benchmark_price", 1850))
                    farmer_db.save_advisory_report(
                        phone_number=self.phone_number,
                        session_id=self.session_id,
                        commodity=comm,
                        best_mandi=top_m,
                        net_profit=round(rate * (dm_session.quantity_quintals or 10.0), 2),
                        summary_text=spoken_text
                    )
            except Exception as e:
                print(f"[VoiceGateway] Supabase turn logging error: {e}")

        # If turn was interrupted during reasoning, abort
        if turn_id != self.active_turn_id:
            print(f"[VoiceGateway:{self.session_id}] Turn {turn_id} discarded due to subsequent interruption")
            return

        # 3. Synthesize & Deliver Response
        await self._synthesize_and_deliver(spoken_text, step=step, extra_data=extra_data, turn_id=turn_id)

    async def _synthesize_and_deliver(self, spoken_text: str, step: str, extra_data: Dict[str, Any], turn_id: Optional[int] = None):
        if turn_id is None:
            turn_id = self.active_turn_id

        # Deliver textual transcript immediately for zero UI lag
        await self.send_json({
            "type": "transcript",
            "role": "agent",
            "text": spoken_text,
            "step": step,
            "data": extra_data,
            "turn_id": turn_id
        })

        # Synthesize audio with Gnani Timbre v3.0
        audio_b64 = None
        key_to_use = self.api_key or settings.GNANI_API_KEY
        if key_to_use and spoken_text:
            await self.send_json({
                "type": "vad_state",
                "state": "synthesizing",
                "message": "Gnani Timbre v3.0: Synthesizing neural Indic speech..."
            })
            try:
                # Run TTS in a cancellable task for instant barge-in support
                tts_lang = "en-IN" if (self.language or "").startswith("en") else (self.language or "hi-IN")
                tts_voice = "Shivani"  # Official Timbre v3.0 voice supporting English (en-IN) and Indic
                tts_coro = gnani_tts.synthesize_speech(
                    spoken_text,
                    lang=tts_lang,
                    voice=tts_voice,
                    api_key=key_to_use
                )
                self.current_tts_task = asyncio.create_task(tts_coro)
                audio_bytes = await self.current_tts_task
                if audio_bytes and len(audio_bytes) > 200:
                    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            except asyncio.CancelledError:
                print(f"[VoiceGateway:{self.session_id}] Timbre TTS cancelled due to barge-in")
                return
            except Exception as e:
                print(f"[VoiceGateway:{self.session_id}] TTS generation error: {e}")

        # Check turn freshness before streaming audio back
        if turn_id != self.active_turn_id:
            print(f"[VoiceGateway:{self.session_id}] Audio discarded for obsolete turn {turn_id}")
            return

        # Stream audio back to client
        await self.send_json({
            "type": "agent_audio",
            "text": spoken_text,
            "audio_base64": audio_b64,
            "step": step,
            "data": extra_data,
            "turn_id": turn_id
        })

        await self.send_json({
            "type": "vad_state",
            "state": "speaking",
            "message": "Gnani Timbre speaking • Barge-in active (speak anytime)"
        })

    def close(self):
        self.is_active = False
        if self.current_tts_task and not self.current_tts_task.done():
            self.current_tts_task.cancel()
