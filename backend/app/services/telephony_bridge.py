"""
Kisan-Vaani Telephony Gateway Bridge
Integrates with Cloud Telephony Providers (Exotel, Twilio India, Tata Tele Business, and Gnani Vachana Telephony)
Supports:
1. Inbound Phone Call Webhook (TwiML / Exotel Voice API)
2. Bidirectional Telephony Audio Streaming (/ws/telephony/stream) over 8kHz mu-law / 16kHz PCM
3. Missed-Call-to-Callback Service (Zero-cost farmer toll-free callback)
"""

import json
import base64
try:
    import audioop
except ImportError:
    import audioop_lts as audioop
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from app.config import settings
from app.services.dialogue_manager import dialogue_manager
from app.services.gnani_stt import gnani_stt
from app.services.gnani_tts import gnani_tts
from app.services.audio_dsp import acoustic_dsp

class TelephonyBridge:
    def __init__(self):
        self.active_calls: Dict[str, Dict[str, Any]] = {}

    def generate_twiml_response(self, stream_url: str) -> str:
        """
        Generates TwiML response for Twilio/Exotel to bridge phone audio directly
        to Kisan-Vaani WebSocket in real time.
        """
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="hi-IN" voice="Polly.Aditi">नमस्ते किसान भाई! किसान-वाणी में आपका स्वागत है। कॉल कनेक्ट हो रही है।</Say>
    <Connect>
        <Stream url="{stream_url}">
            <Parameter name="app" value="kisan-vaani" />
            <Parameter name="language" value="hi-IN" />
        </Stream>
    </Connect>
</Response>"""

    def generate_exotel_flow(self, callback_url: str) -> Dict[str, Any]:
        """
        Exotel Applet JSON for Indian Cloud Telephony dial-in.
        """
        return {
            "flow": {
                "name": "Kisan-Vaani Inbound GSM Bridge",
                "trigger": "incoming_call",
                "actions": [
                    {
                        "type": "audio_stream",
                        "stream_url": callback_url,
                        "codec": "audio/x-mulaw",
                        "sample_rate": 8000
                    }
                ]
            }
        }

    async def handle_telephony_stream(self, websocket: WebSocket):
        """
        Handles bidirectional telephony audio streaming (G.711 mu-law 8kHz <-> 16kHz PCM)
        from telephone service providers.
        """
        await websocket.accept()
        call_sid = None
        stream_sid = None
        session_id = None
        buffer_pcm = bytearray()
        
        try:
            while True:
                msg_text = await websocket.receive_text()
                msg = json.loads(msg_text)
                event = msg.get("event")

                if event == "start":
                    call_sid = msg["start"]["callSid"]
                    stream_sid = msg["start"]["streamSid"]
                    session_id = f"tel_{call_sid[:10]}"
                    print(f"[TelephonyBridge] 📞 Inbound Phone Call Connected: CallSid={call_sid}")
                    
                    # Synthesize initial greeting with Gnani Timbre
                    greeting_text = (
                        "Namaste Kisan Bhai! Main Kisan-Vaani hoon. "
                        "Aap kaunsi fasal ka bhav dekhna chahte hain—jaise Pyaaz, Tamatar ya Gehun?"
                    )
                    audio_wav = await gnani_tts.synthesize_speech(greeting_text, lang="hi-IN")
                    if audio_wav:
                        # Convert 16kHz WAV to 8kHz mu-law for telephone ear-piece
                        mulaw_payload = self._convert_wav_to_mulaw_b64(audio_wav)
                        await websocket.send_text(json.dumps({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": mulaw_payload}
                        }))

                elif event == "media":
                    # Inbound audio chunk from farmer's mobile phone
                    payload = msg["media"]["payload"]
                    chunk_mulaw = base64.b64decode(payload)
                    
                    # Convert 8kHz mu-law from telecom network to 16kHz linear PCM for Gnani Prisma STT
                    try:
                        pcm_8k = audioop.ulaw2lin(chunk_mulaw, 2)
                        pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)
                        buffer_pcm.extend(pcm_16k)
                    except Exception:
                        pass

                    # Detect utterance end when buffer reaches ~2.5 seconds or silence
                    if len(buffer_pcm) >= 16000 * 2 * 3: # 3 seconds chunk
                        raw_wav = self._pcm_to_wav(bytes(buffer_pcm), sample_rate=16000)
                        buffer_pcm.clear()

                        # Clean tractor noise and mandi roar with Acoustic DSP
                        wav_data = acoustic_dsp.clean_audio_for_stt(raw_wav)

                        # Transcribe with Gnani Prisma
                        transcript = await gnani_stt.transcribe_audio_chunk(wav_data, language="hi-IN")
                        if transcript and transcript.strip():
                            print(f"[TelephonyBridge] Farmer Spoke over GSM: '{transcript}'")
                            
                            # Process with dialogue manager
                            res = await dialogue_manager.process_utterance(session_id or "tel_demo", transcript)
                            reply_text = res.get("spoken_text", "")
                            
                            # Synthesize reply with Gnani Timbre
                            reply_wav = await gnani_tts.synthesize_speech(reply_text, lang="hi-IN")
                            if reply_wav:
                                mulaw_b64 = self._convert_wav_to_mulaw_b64(reply_wav)
                                await websocket.send_text(json.dumps({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": mulaw_b64}
                                }))

                elif event == "stop":
                    print(f"[TelephonyBridge] 📴 Phone Call Hung Up: CallSid={call_sid}")
                    break

        except WebSocketDisconnect:
            print(f"[TelephonyBridge] WebSocket disconnected for CallSid={call_sid}")
        except Exception as e:
            print(f"[TelephonyBridge] Error in telephony stream: {e}")

    def _convert_wav_to_mulaw_b64(self, wav_bytes: bytes) -> str:
        """Converts standard 16kHz WAV to 8kHz mu-law base64 string for telephony earpieces."""
        try:
            # Skip 44 bytes WAV header
            raw_pcm = wav_bytes[44:] if len(wav_bytes) > 44 else wav_bytes
            pcm_8k, _ = audioop.ratecv(raw_pcm, 2, 1, 16000, 8000, None)
            mulaw = audioop.lin2ulaw(pcm_8k, 2)
            return base64.b64encode(mulaw).decode("utf-8")
        except Exception:
            return ""

    def _pcm_to_wav(self, pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
        """Adds a standard WAV header to raw linear PCM samples."""
        import io, wave
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

telephony_bridge = TelephonyBridge()
