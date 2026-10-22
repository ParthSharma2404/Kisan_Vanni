import io
import httpx
from typing import Optional
from app.config import settings

class GnaniSTTService:
    def __init__(self):
        self.api_url = settings.GNANI_STT_API_URL

    async def transcribe_audio_chunk(
        self,
        audio_bytes: bytes,
        language: str = "hi-IN",
        api_key: Optional[str] = None
    ) -> str:
        """
        Sends audio to Gnani Prisma STT v3 API (api.vachana.ai/stt/v3).
        Header: X-API-Key-ID: <key>
        """
        key_to_use = api_key or settings.GNANI_API_KEY
        if not key_to_use:
            return ""

        headers = {
            "X-API-Key-ID": key_to_use.strip()
        }
        files = {
            "audio_file": ("audio.wav", audio_bytes, "audio/wav")
        }
        data = {
            "language_code": language,
            "format": "transcribe",
            "itn_native_numerals": "true"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(self.api_url, headers=headers, files=files, data=data)
                if res.status_code == 200:
                    result = res.json()
                    transcript = result.get("transcript") or result.get("text") or ""
                    print(f"[GnaniSTT] Prisma Transcript: {transcript}")
                    return transcript
                else:
                    print(f"[GnaniSTT] API returned status {res.status_code}: {res.text}")
        except Exception as e:
            print(f"[GnaniSTT] Error connecting to Prisma API: {e}")

        return ""

gnani_stt = GnaniSTTService()
