import io
import wave
import asyncio
import httpx
from typing import Optional
from app.config import settings

SUPPORTED_VOICES = {
    "shivani": "Shivani",
    "riyaa": "Riyaa",
    "tarika": "Tarika",
    "lakshmi": "Lakshmi",
    "kalpana": "Kalpana",
    "chetana": "Chetana",
    "vasudha": "Vasudha",
    "avinash": "Avinash",
    "shubham": "Shubham",
    "prakash": "Prakash",
    "devansh": "Devansh",
    "yashraj": "Yashraj",
    "harshad": "Harshad"
}

def normalize_voice(voice: Optional[str]) -> str:
    if not voice:
        return "Shivani"
    v_clean = voice.strip().lower()
    return SUPPORTED_VOICES.get(v_clean, "Shivani")

def normalize_lang(lang: Optional[str]) -> str:
    if not lang:
        return "hi-IN"
    l_clean = lang.strip().lower()
    if l_clean.startswith("en"):
        return "en-IN"
    if l_clean == "hinglish":
        return "hi-IN"
    return lang.strip()

class GnaniTTSService:
    def __init__(self):
        self.api_url = settings.GNANI_TTS_API_URL

    async def synthesize_speech(
        self,
        text: str,
        lang: str = "hi-IN",
        voice: str = "Shivani",
        api_key: Optional[str] = None
    ) -> bytes:
        """
        Synthesizes text to speech using official Gnani Timbre v3.0 API (api.vachana.ai).
        Header: X-API-Key-ID: <key>
        """
        key_to_use = api_key or settings.GNANI_API_KEY

        if key_to_use:
            clean_lang = normalize_lang(lang)
            clean_voice = normalize_voice(voice)

            headers = {
                "X-API-Key-ID": key_to_use.strip(),
                "Content-Type": "application/json"
            }

            # Clean special characters like ₹ to avoid mispronunciations in English vs Indic
            if clean_lang == "en-IN":
                cleaned_text = text.replace("₹", " rupees ").replace("Rs.", " rupees ")
            else:
                cleaned_text = text.replace("₹", "रुपये ").replace("Rs.", "रुपये ")

            payload = {
                "text": cleaned_text,
                "language": clean_lang,
                "model": "timbre-v3.0",
                "voice": clean_voice,
                "speed": 1.0,
                "audio_config": {
                    "encoding": "linear_pcm",
                    "container": "wav",
                    "num_channels": 1,
                    "sample_rate": 16000,
                    "sample_width": 2
                }
            }

            try:
                async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                    res = await client.post(self.api_url, headers=headers, json=payload)
                    if res.status_code == 200 and len(res.content) > 100:
                        print(f"[GnaniTTS] Successfully synthesized {len(res.content)} bytes from Timbre v3.0 ({clean_voice}, {clean_lang})")
                        return res.content
                    elif res.status_code == 429:
                        print(f"[GnaniTTS] Rate limited (429). Retrying after 0.8s backoff...")
                        await asyncio.sleep(0.8)
                        retry_res = await client.post(self.api_url, headers=headers, json=payload)
                        if retry_res.status_code == 200 and len(retry_res.content) > 100:
                            print(f"[GnaniTTS] Backoff retry synthesis successful: {len(retry_res.content)} bytes")
                            return retry_res.content
                    elif res.status_code != 200 and clean_voice != "Shivani":
                        # Automatic failover to primary neural voice Shivani
                        print(f"[GnaniTTS] Retry with primary voice Shivani for {clean_lang}")
                        payload["voice"] = "Shivani"
                        retry_res = await client.post(self.api_url, headers=headers, json=payload)
                        if retry_res.status_code == 200 and len(retry_res.content) > 100:
                            print(f"[GnaniTTS] Failover synthesis successful: {len(retry_res.content)} bytes")
                            return retry_res.content
                    else:
                        print(f"[GnaniTTS] API returned status {res.status_code}: {res.text}")
            except Exception as e:
                print(f"[GnaniTTS] Error connecting to Timbre TTS API: {e}")

        # Return empty bytes on failure so frontend handles gracefully
        return b""

gnani_tts = GnaniTTSService()
