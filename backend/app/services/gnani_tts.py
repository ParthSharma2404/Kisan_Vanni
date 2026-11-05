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

def clean_for_speech(text: str) -> str:
    """
    Cleans text for natural neural speech synthesis (Gnani Timbre v3.0).
    Strips raw markdown syntax (bold asterisks, headers, backticks, bullet symbols, table pipes, URLs)
    while strictly preserving every single word, chemical cure, dosage, price, and punctuation.
    """
    if not text:
        return ""
    import re
    # Remove URLs
    cleaned = re.sub(r'https?://\S+', '', text)
    # Remove markdown link formatting [text](url) -> text
    cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)
    # Remove markdown bold, italic, code marks, headers, blockquotes
    cleaned = re.sub(r'[*_`#~>]', '', cleaned)
    # Remove bullet points or list markers at line starts
    cleaned = re.sub(r'^\s*[-•*]\s+', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'^\s*\d+\.\s+', '', cleaned, flags=re.MULTILINE)
    # Remove table divider lines and pipes
    cleaned = re.sub(r'\|', ' ', cleaned)
    cleaned = re.sub(r'---+', '', cleaned)
    # Replace newlines with clean sentence pauses
    cleaned = re.sub(r'\n+', '. ', cleaned)
    # Clean up duplicate periods or spaces
    cleaned = re.sub(r'\.\s*\.', '.', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

class GnaniTTSService:
    def __init__(self):
        self.api_url = settings.GNANI_TTS_API_URL
        self._client: Optional[httpx.AsyncClient] = None
        self._cache: dict = {}

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(12.0, connect=3.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=40, keepalive_expiry=180.0),
                verify=False
            )
        return self._client

    async def pre_warm(self):
        """Pre-warm persistent TCP/TLS connection to api.vachana.ai on startup."""
        try:
            key_to_use = settings.GNANI_API_KEY
            if not key_to_use:
                return
            client = await self.get_client()
            headers = {
                "X-API-Key-ID": key_to_use.strip(),
                "Content-Type": "application/json"
            }
            payload = {
                "text": "Hello Kisan",
                "language": "en-IN",
                "model": "timbre-v3.0",
                "voice": "Shivani",
                "speed": 1.0,
                "audio_config": {
                    "encoding": "linear_pcm",
                    "container": "wav",
                    "num_channels": 1,
                    "sample_rate": 16000,
                    "sample_width": 2
                }
            }
            res = await client.post(self.api_url, headers=headers, json=payload)
            if res.status_code == 200 and len(res.content) > 100:
                self._cache["en-IN:Shivani:Hello Kisan"] = res.content
                print("[GnaniTTS] Pre-warmed persistent connection to Timbre v3.0 successfully.")
        except Exception as e:
            print(f"[GnaniTTS] Pre-warm notice: {e}")

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
        if not text or not text.strip():
            return b""

        key_to_use = api_key or settings.GNANI_API_KEY

        if key_to_use:
            clean_lang = normalize_lang(lang)
            clean_voice = normalize_voice(voice)

            # Strip markdown noise while preserving 100% of the words, dosages, and prices
            cleaned_text = clean_for_speech(text)

            # Clean special characters like ₹ to avoid mispronunciations in English vs Indic
            if clean_lang == "en-IN":
                cleaned_text = cleaned_text.replace("₹", " rupees ").replace("Rs.", " rupees ")
            else:
                cleaned_text = cleaned_text.replace("₹", "रुपये ").replace("Rs.", "रुपये ")

            # Check in-memory audio cache for 0ms instant playback
            cache_key = f"{clean_lang}:{clean_voice}:{cleaned_text.strip()}"
            if cache_key in self._cache:
                print(f"[GnaniTTS] Cache hit for '{cleaned_text[:35]}...' (0ms instant playback)")
                return self._cache[cache_key]

            headers = {
                "X-API-Key-ID": key_to_use.strip(),
                "Content-Type": "application/json"
            }

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
                client = await self.get_client()
                res = await client.post(self.api_url, headers=headers, json=payload)
                if res.status_code == 200 and len(res.content) > 100:
                    print(f"[GnaniTTS] Successfully synthesized {len(res.content)} bytes from Timbre v3.0 ({clean_voice}, {clean_lang})")
                    if len(self._cache) > 200:
                        self._cache.clear()
                    self._cache[cache_key] = res.content
                    return res.content
                elif res.status_code == 429:
                    print(f"[GnaniTTS] Rate limited (429). Retrying after 0.5s backoff...")
                    await asyncio.sleep(0.5)
                    retry_res = await client.post(self.api_url, headers=headers, json=payload)
                    if retry_res.status_code == 200 and len(retry_res.content) > 100:
                        print(f"[GnaniTTS] Backoff retry synthesis successful: {len(retry_res.content)} bytes")
                        self._cache[cache_key] = retry_res.content
                        return retry_res.content
                elif res.status_code != 200 and clean_voice != "Shivani":
                    # Automatic failover to primary neural voice Shivani
                    print(f"[GnaniTTS] Retry with primary voice Shivani for {clean_lang}")
                    payload["voice"] = "Shivani"
                    retry_res = await client.post(self.api_url, headers=headers, json=payload)
                    if retry_res.status_code == 200 and len(retry_res.content) > 100:
                        print(f"[GnaniTTS] Failover synthesis successful: {len(retry_res.content)} bytes")
                        self._cache[cache_key] = retry_res.content
                        return retry_res.content
                else:
                    print(f"[GnaniTTS] API returned status {res.status_code}: {res.text}")
            except Exception as e:
                print(f"[GnaniTTS] Error connecting to Timbre TTS API: {e}")

        # Return empty bytes on failure so frontend handles gracefully
        return b""

gnani_tts = GnaniTTSService()
