"""
Kisan-Vaani Superpowered Speech-to-Text (STT) Engine with Anti-Urdu Firewall
Dual-Engine Architecture:
1. Groq Whisper Large v3 (whisper-large-v3): World-class multilingual speech recognition with zero word drops, agricultural vocabulary biasing, and deep Indic accent understanding.
2. Gnani Prisma v3 (api.vachana.ai/stt/v3): Native Sovereign Indic STT model.
3. Anti-Urdu Unicode Firewall: Completely prevents any Arabic/Urdu script output.
"""

import io
import os
import re
import httpx
import asyncio
from typing import Optional, Dict, Any
from app.config import settings

# Unicode ranges covering Arabic, Urdu, Persian characters
URDU_ARABIC_REGEX = re.compile(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]')

class SuperpoweredSTTService:
    def __init__(self):
        self.api_url = settings.GNANI_STT_API_URL
        self.groq_api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "").strip()

    def clean_hallucinations(self, text: str) -> str:
        """
        Strips common Whisper training dataset artifacts (YouTube end-screen subtitles).
        When audio has low energy or trailing silence, Whisper often hallucinates phrases like
        'Thank you for watching', 'Please like and subscribe', etc.
        """
        if not text:
            return ""
        
        cleaned = text.strip()
        
        # Regex patterns matching trailing YouTube end-card hallucinations
        hallucination_patterns = [
            r"(?:thank\s+you\s+(?:very\s+much\s+)?(?:so\s+much\s+)?for\s+watching[.!?,]*\s*)+$",
            r"(?:thanks\s+for\s+watching[.!?,]*\s*)+$",
            r"(?:please\s+like\s+and\s+subscribe[.!?,]*\s*)+$",
            r"(?:like\s+and\s+subscribe[.!?,]*\s*)+$",
            r"(?:subscribe\s+to\s+(?:my\s+)?channel[.!?,]*\s*)+$",
            r"(?:subtitles\s+by[^\n.]*[.!?,]*\s*)+$",
            r"(?:translated\s+by[^\n.]*[.!?,]*\s*)+$",
            r"(?:amara\.org[.!?,]*\s*)+$",
        ]
        for pat in hallucination_patterns:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
            
        lower_t = cleaned.lower().strip(" .!?,:;\"'()[]{}")
        standalone_hallucinations = {
            "thank you for watching",
            "thanks for watching",
            "thank you very much for watching",
            "thank you so much for watching",
            "thank you",
            "thanks",
            "thank you very much",
            "please like and subscribe",
            "like and subscribe",
            "subscribe for more",
            "subtitles by",
            "translated by",
            "amara.org",
            "bye",
            "bye bye",
            "see you next time",
            "you"
        }
        if lower_t in standalone_hallucinations:
            return ""

        return cleaned

    def _normalize_gnani_lang(self, lang: str) -> str:
        """
        Gnani Prisma v3 strictly accepts only these codes:
        as-IN, bn-IN, en-IN, gu-IN, hi-IN, indic-auto, kn-IN, ml-IN, mr-IN, pa-IN, ta-IN, te-IN.
        Sending 'en-US' or 'hinglish' causes HTTP 400 INVALID_LANGUAGE_CODE.
        """
        l = (lang or "").lower().strip()
        if "en" in l:
            return "en-IN"
        if "pa" in l:
            return "pa-IN"
        if "hi" in l:
            return "hi-IN"
        if "mr" in l:
            return "mr-IN"
        if "te" in l:
            return "te-IN"
        if "ta" in l:
            return "ta-IN"
        if "gu" in l:
            return "gu-IN"
        if "bn" in l:
            return "bn-IN"
        if "hinglish" in l:
            return "hi-IN"
        return "indic-auto"

    def _normalize_whisper_lang(self, lang: str) -> str:
        """
        Maps Kisan-Vaani language codes to ISO-639-1 for Whisper Large v3.
        NEVER returns None or 'ur' - always forces either target Indic language, Hindi, or English!
        """
        l = (lang or "").lower().strip()
        if "pa" in l:
            return "pa"
        if "mr" in l:
            return "mr"
        if "te" in l:
            return "te"
        if "ta" in l:
            return "ta"
        if "gu" in l:
            return "gu"
        if "bn" in l:
            return "bn"
        if "en" in l and "hi" not in l and "hinglish" not in l:
            return "en"
        # For Hindi, Hinglish, or any unspecified code: STRICTLY force "hi" (Hindi)
        # Prevents Whisper's language detector from mistakenly selecting "ur" (Urdu)
        return "hi"

    async def _sanitize_anti_urdu(self, text: str) -> str:
        """
        Anti-Urdu Unicode Firewall:
        If any Arabic/Perso-Arabic glyph is present in the transcript,
        instantly transliterates/converts it to clean Hindi Devanagari or Latin text.
        """
        if not text or not URDU_ARABIC_REGEX.search(text):
            return text

        groq_key = self.groq_api_key or os.getenv("GROQ_API_KEY", "").strip() or settings.GROQ_API_KEY
        if groq_key:
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    res = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {groq_key.strip()}"},
                        json={
                            "model": "llama-3.3-70b-versatile",
                            "messages": [
                                {
                                    "role": "system",
                                    "content": (
                                        "You are an Indic language normalizer for an Indian farmer app. "
                                        "The user's speech was mistakenly transcribed in Urdu/Arabic script. "
                                        "Convert this Urdu text into clean Hindi (Devanagari script or Hinglish Latin). "
                                        "NEVER use Arabic or Urdu letters. Output ONLY the converted text."
                                    )
                                },
                                {"role": "user", "content": text}
                            ],
                            "temperature": 0.0,
                            "max_tokens": 120
                        }
                    )
                    if res.status_code == 200:
                        converted = res.json()["choices"][0]["message"]["content"].strip()
                        if not URDU_ARABIC_REGEX.search(converted):
                            print(f"[STT:AntiUrdu] Converted Urdu '{text}' -> Hindi '{converted}'")
                            return converted
            except Exception as e:
                print(f"[STT:AntiUrdu] Conversion notice: {e}")

        # Fallback safety: strip any Arabic/Urdu codepoints completely
        cleaned = URDU_ARABIC_REGEX.sub('', text).strip()
        return cleaned

    async def transcribe_with_whisper(self, audio_bytes: bytes, language: str = "en-IN") -> str:
        """
        Transcribes speech using Groq's Whisper Large v3 with agricultural vocabulary prompting.
        Ultra-fast (< 300ms) and recognizes Indian accents, rural terminology, and code-switched phrasing.
        """
        groq_key = self.groq_api_key or os.getenv("GROQ_API_KEY", "").strip() or settings.GROQ_API_KEY
        if not groq_key or not audio_bytes or len(audio_bytes) < 400:
            return ""

        w_lang = self._normalize_whisper_lang(language)

        headers = {
            "Authorization": f"Bearer {groq_key.strip()}"
        }
        files = {
            "file": ("audio.wav", audio_bytes, "audio/wav")
        }
        data = {
            "model": "whisper-large-v3",
            "prompt": (
                "Kisan-Vaani Indian agricultural advisor. Mandi bhav, APMC rates, eNAM, quintal, "
                "crop advisory, gehun, pyaaz, tamatar, aloo, fasal, kisan, khad, urea, DAP, spray, "
                "bhav, bhao, Lasalgaon, Azadpur, Indore, Vashi, mandi, price, yesterday, today, Mohali, Lalru, Hardaspur. "
                "Transcribe in standard Hindi Devanagari or English Latin script only. Do NOT use Urdu script."
            ),
            "temperature": "0.0",
            "language": w_lang
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data
                )
                if res.status_code == 200:
                    text = res.json().get("text", "").strip()
                    cleaned_hallucinations = self.clean_hallucinations(text)
                    if not cleaned_hallucinations:
                        return ""
                    
                    # Run through Anti-Urdu Firewall
                    clean_text = await self._sanitize_anti_urdu(cleaned_hallucinations)
                    print(f"[SuperSTT:Whisper] Detected: '{clean_text}' (forced_lang={w_lang})")
                    return clean_text
                else:
                    print(f"[SuperSTT:Whisper] API error {res.status_code}: {res.text[:120]}")
        except Exception as e:
            print(f"[SuperSTT:Whisper] Notice: {e}")

        return ""

    async def transcribe_with_gnani(
        self,
        audio_bytes: bytes,
        language: str = "hi-IN",
        api_key: Optional[str] = None
    ) -> str:
        """
        Transcribes speech using Gnani Prisma STT v3 API with corrected Indic language codes.
        """
        key_to_use = api_key or settings.GNANI_API_KEY
        if not key_to_use or not audio_bytes or len(audio_bytes) < 400:
            return ""

        gnani_lang = self._normalize_gnani_lang(language)
        headers = {
            "X-API-Key-ID": key_to_use.strip()
        }
        files = {
            "audio_file": ("audio.wav", audio_bytes, "audio/wav")
        }
        data = {
            "language_code": gnani_lang,
            "format": "transcribe",
            "itn_native_numerals": "true"
        }

        try:
            async with httpx.AsyncClient(timeout=14.0, verify=False) as client:
                res = await client.post(self.api_url, headers=headers, files=files, data=data)
                if res.status_code == 200:
                    result = res.json()
                    transcript = (result.get("transcript") or result.get("text") or "").strip()
                    if transcript:
                        clean_text = await self._sanitize_anti_urdu(transcript)
                        print(f"[SuperSTT:GnaniPrisma] Detected: '{clean_text}' (lang={gnani_lang})")
                        return clean_text
                else:
                    print(f"[SuperSTT:GnaniPrisma] Status {res.status_code}: {res.text[:120]}")
        except Exception as e:
            print(f"[SuperSTT:GnaniPrisma] Notice: {e}")

        return ""

    async def transcribe_audio_chunk(
        self,
        audio_bytes: bytes,
        language: str = "en-IN",
        api_key: Optional[str] = None
    ) -> str:
        """
        Transcribes speech prioritizing Gnani Prisma STT v3 as the primary engine
        to detect the exact Indic words spoken by the farmer.
        Falls back to Groq Whisper Large v3 if Gnani Prisma produces no transcript.
        """
        if not audio_bytes or len(audio_bytes) < 300:
            return ""

        # Launch Gnani Prisma (Primary) and Whisper (Fallback) concurrently
        tasks = [
            self.transcribe_with_gnani(audio_bytes, language=language, api_key=api_key),
            self.transcribe_with_whisper(audio_bytes, language=language)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        gnani_text = results[0] if isinstance(results[0], str) else ""
        whisper_text = results[1] if isinstance(results[1], str) else ""

        # Priority 1: Gnani Prisma STT v3 (Exact Sovereign Indic Model)
        if gnani_text and len(gnani_text.strip()) > 1:
            clean_g = self.clean_hallucinations(gnani_text.strip())
            if clean_g:
                print(f"[SuperSTT] Utilizing Gnani Prisma v3 transcript: '{clean_g}'")
                return clean_g

        # Priority 2: Whisper Large v3 Fallback
        if whisper_text and len(whisper_text.strip()) > 1:
            clean_w = self.clean_hallucinations(whisper_text.strip())
            if clean_w:
                print(f"[SuperSTT] Utilizing Whisper fallback transcript: '{clean_w}'")
                return clean_w

        return ""

gnani_stt = SuperpoweredSTTService()
