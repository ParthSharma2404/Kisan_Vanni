import sys
import os
import json
import base64
import urllib.parse
import httpx
import asyncio

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from app.config import settings
from app.services.dialogue_manager import dialogue_manager
from app.services.gnani_stt import gnani_stt
from app.services.gnani_tts import gnani_tts
from app.services.mandi_service import mandi_service
from app.services.voice_gateway import VoiceGatewaySession

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for Kisan-Vaani: Full-Duplex Voice Gateway, Mandi Arbitrage & eNAM Advisor"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend directory for direct UI access
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/app", StaticFiles(directory=frontend_dir, html=True), name="static_frontend")

class ChatRequest(BaseModel):
    session_id: str
    utterance: str
    language: Optional[str] = "hi-IN"
    api_key: Optional[str] = None

class TTSRequest(BaseModel):
    text: str
    language: Optional[str] = "hi-IN"
    voice: Optional[str] = "Shivani"
    api_key: Optional[str] = None

class KeyConfigRequest(BaseModel):
    api_key: str

@app.get("/")
async def root():
    return RedirectResponse(url="/app/")

async def periodic_daily_mandi_sync():
    """
    Automated background worker:
    1. Pre-fetches today's live Agmarknet mandi rates for staple crops.
    2. Automatically repeats every 6 hours so the cache stays fresh with daily market arrivals.
    """
    staple_crops = ["Onion", "Tomato", "Wheat", "Potato", "Soyabean", "Bengal Gram(Gram)(Whole)"]
    while True:
        try:
            print("[PeriodicSync] Running scheduled background sync for live Agmarknet mandi rates...")
            for crop in staple_crops:
                await mandi_service.fetch_rates_from_gov_api(commodity=crop, limit=35)
                await asyncio.sleep(2.0)  # Gentle pacing to respect data.gov.in rate limits
            print("[PeriodicSync] Scheduled Agmarknet sync completed successfully.")
        except Exception as e:
            print(f"[PeriodicSync] Background sync notice: {e}")
        
        # Refresh every 6 hours (matches morning and evening APMC auction sessions)
        await asyncio.sleep(6 * 3600)

@app.on_event("startup")
async def startup_prewarm():
    """Pre-warm live data and AI client in background on startup."""
    try:
        # 1. Start continuous periodic Agmarknet synchronization
        asyncio.create_task(periodic_daily_mandi_sync())
        # 2. Pre-connect Gnani Evon client in worker thread so first query has zero latency
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, llm_service._get_evon_client)
        print("[Startup] Live Government data sync & Gnani Evon pre-warm initiated.")
    except Exception as e:
        print(f"[Startup] Pre-warm notice: {e}")


from app.services.llm_service import llm_service

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "gnani_api_key_configured": bool(settings.GNANI_API_KEY),
        "gnani_evon_llm_configured": bool(settings.HF_TOKEN or settings.EVON_SPACE_ID),
        "evon_space_id": settings.EVON_SPACE_ID,
        "gnani_stt_url": settings.GNANI_STT_API_URL,
        "gnani_tts_url": settings.GNANI_TTS_API_URL,
        "websocket_endpoint": "/ws/call",
        "vad_mode": "full_duplex_barge_in"
    }

@app.post("/api/config/key")
async def save_api_key(req: KeyConfigRequest):
    key = req.api_key.strip()
    settings.GNANI_API_KEY = key
    
    # Save to backend/.env
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"GNANI_API_KEY={key}\n")
    except Exception as e:
        print(f"Could not persist .env: {e}")
        
    return {"status": "saved", "configured": bool(key)}

class LLMGenerateRequest(BaseModel):
    query: str
    farmer_name: Optional[str] = "Kisan Bhai"
    village: Optional[str] = ""
    district: Optional[str] = ""
    crops: Optional[list] = None

class SummaryRequest(BaseModel):
    session_id: str
    phone_number: Optional[str] = ""

@app.post("/api/session/whatsapp_summary")
async def trigger_whatsapp_summary(req: SummaryRequest):
    session = dialogue_manager.get_or_create_session(req.session_id)
    if req.phone_number:
        session.phone_number = req.phone_number
    summary_data = dialogue_manager.generate_daily_crux_summary(session)
    return {
        "status": "success",
        "summary": summary_data
    }

# =====================================================================
# FULL-DUPLEX WEBSOCKET VOICE GATEWAY WITH REAL-TIME BARGE-IN (VAD)
# =====================================================================
@app.websocket("/ws/call")
async def websocket_call_endpoint(websocket: WebSocket):
    """
    Production-grade Full-Duplex Voice Gateway:
    - Streams bidirectional audio & event packets.
    - Zero-lag Barge-In cancellation when farmer speaks.
    - Dynamic silence auto-commit (700ms pause).
    """
    await websocket.accept()
    session_id = f"call_{int(os.times().system * 1000)}"
    gateway = VoiceGatewaySession(websocket, session_id)
    print(f"[WebSocket] Connected client on /ws/call (session={session_id})")

    try:
        while True:
            raw_msg = await websocket.receive_text()
            try:
                data = json.loads(raw_msg)
            except Exception:
                continue

            msg_type = data.get("type", "")

            if msg_type == "start_call":
                if data.get("session_id"):
                    gateway.session_id = data["session_id"]
                await gateway.handle_start_call(data)

            elif msg_type == "speech_start":
                # Farmer started speaking -> trigger instant barge-in cancel
                await gateway.handle_speech_start()

            elif msg_type == "interrupt":
                await gateway.handle_interrupt(data)

            elif msg_type == "speech_end":
                # Farmer finished speaking (700ms pause)
                await gateway.handle_speech_end(data)

            elif msg_type == "user_text":
                await gateway.handle_user_text(data)

            elif msg_type == "set_language":
                lang = data.get("language", "en-US")
                gateway.language = lang
                dm_session = dialogue_manager.get_or_create_session(gateway.session_id)
                dm_session.language = lang
                if gateway.phone_number:
                    try:
                        farmer_db.update_farmer_profile(gateway.phone_number, language=lang)
                    except Exception as e:
                        print(f"[Main] Language profile update error: {e}")
                await gateway.send_json({"type": "language_updated", "language": lang})

            elif msg_type == "reset_session":
                dialogue_manager.reset_session(gateway.session_id)
                await gateway.send_json({"type": "session_reset", "session_id": gateway.session_id})

            elif msg_type == "ping":
                await gateway.send_json({"type": "pong"})

    except WebSocketDisconnect:
        print(f"[WebSocket] Disconnected (session={gateway.session_id})")
    except Exception as e:
        print(f"[WebSocket] Error in session {gateway.session_id}: {e}")
    finally:
        gateway.close()

# =====================================================================
# REST FALLBACK & INTELLIGENCE ENDPOINTS
# =====================================================================
@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """
    REST fallback for text or turn-based speech input.
    """
    if req.api_key:
        settings.GNANI_API_KEY = req.api_key.strip()

    session = dialogue_manager.get_or_create_session(req.session_id)
    if req.language:
        session.language = req.language

    res = await dialogue_manager.process_utterance(req.session_id, req.utterance)
    
    spoken_text = res.get("spoken_text", "")
    audio_base64 = None
    if settings.GNANI_API_KEY and spoken_text:
        try:
            audio_bytes = await gnani_tts.synthesize_speech(
                spoken_text,
                lang=req.language or "hi-IN",
                api_key=settings.GNANI_API_KEY
            )
            if audio_bytes and len(audio_bytes) > 200:
                audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        except Exception as e:
            print(f"[Main] TTS generation error: {e}")

    res["audio_base64"] = audio_base64
    res["gnani_configured"] = bool(settings.GNANI_API_KEY)
    return res

@app.post("/api/tts")
async def tts_endpoint(req: TTSRequest):
    """
    Synthesize speech using official Gnani Timbre v3.0 API.
    """
    audio_bytes = await gnani_tts.synthesize_speech(
        req.text,
        lang=req.language or "hi-IN",
        voice=req.voice or "Shivani",
        api_key=req.api_key or settings.GNANI_API_KEY
    )
    return Response(content=audio_bytes, media_type="audio/wav")

@app.post("/api/stt")
async def stt_endpoint(
    audio_file: UploadFile = File(...),
    language: str = Form("hi-IN"),
    api_key: Optional[str] = Form(None)
):
    """
    Transcribe audio file using official Gnani Prisma v3 STT API.
    """
    audio_bytes = await audio_file.read()
    transcript = await gnani_stt.transcribe_audio_chunk(
        audio_bytes,
        language=language,
        api_key=api_key or settings.GNANI_API_KEY
    )
    return {"transcript": transcript}

@app.post("/api/reset")
async def reset_session(session_id: str):
    dialogue_manager.reset_session(session_id)
    return {"status": "reset", "session_id": session_id}

@app.get("/api/mandis")
async def get_mandis(commodity: str = "onion", lat: float = 20.0800, lon: float = 74.1100, live: bool = True):
    if live and settings.DATA_GOV_API_KEY:
        try:
            await mandi_service.fetch_rates_from_gov_api(commodity=commodity, limit=20)
        except Exception as e:
            print(f"[Main:Mandi] Live fetch error: {e}")
    rates = mandi_service.get_rates_for_commodity(commodity, lat, lon)
    return {
        "commodity": commodity,
        "mandis": rates,
        "live_gov_connected": bool(settings.DATA_GOV_API_KEY),
        "source": "Ministry of Agriculture Open Data (data.gov.in) & Geospatial APMC Radar"
    }

@app.get("/api/mandis/live-sync")
async def live_sync_mandis(state: str = "Maharashtra", commodity: Optional[str] = None):
    """Direct verification endpoint for data.gov.in live Agmarknet daily price feed."""
    records = await mandi_service.fetch_rates_from_gov_api(state=state, commodity=commodity, limit=50)
    return {
        "status": "synced",
        "live_gov_connected": bool(settings.DATA_GOV_API_KEY),
        "records_count": len(records),
        "source": "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070",
        "records": records[:10]
    }

from app.services.telephony_bridge import telephony_bridge

@app.get("/api/slip/{session_id}")
async def get_slip(session_id: str):
    session = dialogue_manager.get_or_create_session(session_id)
    return {"slip": session.mandi_slip, "evaluated_mandis": session.last_arbitrage_results}

@app.get("/api/session/history/{session_id}")
async def get_session_history(session_id: str):
    """Retrieve full in-memory chat history and evaluated data for zero-loss session restoration."""
    session = dialogue_manager.get_or_create_session(session_id)
    return {
        "session_id": session_id,
        "chat_history": session.chat_history,
        "language": getattr(session, "language", "en-US"),
        "commodity": session.commodity,
        "last_arbitrage_results": session.last_arbitrage_results
    }

class TranslateSessionRequest(BaseModel):
    session_id: str
    target_language: str
    turns: Optional[List[Dict[str, Any]]] = None

@app.post("/api/session/translate")
async def translate_session_endpoint(req: TranslateSessionRequest):
    """
    Seamlessly translate the entire conversation history into the user's selected language.
    Preserves all agricultural entities (mandi rates, APMC names, eNAM rules, ICAR dosages).
    """
    res = await dialogue_manager.translate_session(
        session_id=req.session_id,
        target_language=req.target_language,
        turns=req.turns
    )
    return {
        "status": "success",
        "session_id": req.session_id,
        "target_language": req.target_language,
        "translated_turns": res
    }

# =====================================================================
# FARMER ASSISTANT DATABASE & QUERY MEMORY
# =====================================================================
from app.services.farmer_db import farmer_db

class SwitchFarmerRequest(BaseModel):
    phone_number: str
    session_id: Optional[str] = None

class WhatsAppDispatchRequest(BaseModel):
    phone_number: str = ""
    session_id: Optional[str] = None
    custom_message: Optional[str] = None

@app.get("/api/farmers")
async def get_all_farmers():
    """List all registered farmers with their acreage, village and primary crops."""
    return {"farmers": farmer_db.get_all_farmers()}

@app.get("/api/farmers/{phone_number}")
async def get_farmer_profile(phone_number: str):
    """Retrieve farmer profile, historical queries, and personalized conversational greeting."""
    farmer = farmer_db.get_farmer(phone_number)
    history = farmer_db.get_farmer_history(phone_number)
    greeting_res = farmer_db.get_personalized_greeting(phone_number)
    return {
        "farmer": farmer,
        "is_new": greeting_res["is_new"],
        "history": history,
        "personalized_greeting": greeting_res["greeting_text"]
    }

@app.post("/api/farmers/switch")
async def switch_farmer(req: SwitchFarmerRequest):
    """Switches active farmer in session memory and generates personalized greeting."""
    farmer = farmer_db.get_farmer(req.phone_number)
    greeting_res = farmer_db.get_personalized_greeting(req.phone_number)
    
    if req.session_id:
        session = dialogue_manager.get_or_create_session(req.session_id)
        session.phone_number = req.phone_number
        if farmer:
            session.farmer_name = farmer.get("name", "Kisan Bhai")
            session.district = farmer.get("district", "Nashik")
            session.location_name = farmer.get("village", "")
            session.step = "CONFIRMING_LOCATION"
        else:
            session.farmer_name = "Kisan Bhai"
            session.step = "ONBOARDING_PROFILE"
    
    return {
        "status": "switched",
        "farmer": farmer,
        "is_new": greeting_res["is_new"],
        "personalized_greeting": greeting_res["greeting_text"]
    }

# =====================================================================
# WHATSAPP BAILEYS AUTOMATIC DISPATCHER
# =====================================================================
@app.get("/api/whatsapp/status")
async def whatsapp_status():
    """Checks whether local Node Baileys WhatsApp bot is connected."""
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            res = await client.get("http://localhost:5005/api/whatsapp/status")
            if res.status_code == 200:
                return res.json()
    except Exception:
        pass
    return {
        "status": "offline_or_standalone",
        "target_phone": "farmer_mobile",
        "has_qr": False,
        "message": "Baileys microservice is running in standby. WhatsApp Web deep-link active."
    }

@app.post("/api/whatsapp/dispatch")
async def dispatch_whatsapp(req: WhatsAppDispatchRequest):
    """
    Sends the digital reasoning slip directly to the farmer's WhatsApp
    via Node Baileys socket. If Baileys isn't paired yet, returns the instant WhatsApp Web URL.
    """
    phone = req.phone_number or "919999999999"
    message_text = req.custom_message

    if not message_text and req.session_id:
        session = dialogue_manager.get_or_create_session(req.session_id)
        if session.mandi_slip and session.mandi_slip.get("whatsapp_text"):
            message_text = session.mandi_slip["whatsapp_text"]

    if not message_text:
        message_text = (
            "*KISAN-VAANI MANDI & ADVISORY REPORT*\n"
            "किसान भाई, आपकी फसल का आज का सर्वोत्तम मंडी भाव एवं ई-नाम अधिकार रिपोर्ट:\n\n"
            "• *सर्वोत्तम मंडी:* Lasalgaon APMC\n"
            "• *रेट:* ₹2,450 / क्विंटल\n"
            "• *कमीशन:* ₹0 (ई-नाम कानून के तहत व्यापारी देगा)\n"
            "• *शुद्ध मुनाफा:* +₹1,850 अतिरिक्त लाभ!\n\n"
            "सरकारी हेल्पलाइन: 1800-270-0224 (eNAM)"
        )

    clean_phone = phone.replace("+91", "").replace(" ", "").replace("-", "").strip()
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone

    fallback_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={urllib.parse.quote(message_text)}"

    # Attempt delivery via Node.js Baileys service if running
    baileys_delivered = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            res = await client.post("http://localhost:5005/api/whatsapp/send", json={
                "phone": clean_phone,
                "message": message_text
            })
            if res.status_code == 200 and res.json().get("success"):
                baileys_delivered = True
    except Exception:
        pass

    return {
        "success": True,
        "delivered_via_baileys": baileys_delivered,
        "phone_number": clean_phone,
        "whatsapp_url": fallback_url,
        "message": "Advisory slip ready for WhatsApp! Sent via Baileys." if baileys_delivered else "Dispatched to WhatsApp Web."
    }

