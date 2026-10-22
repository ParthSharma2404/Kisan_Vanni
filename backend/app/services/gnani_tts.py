import io
import wave
import httpx
from typing import Optional
from app.config import settings

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
            headers = {
                "X-API-Key-ID": key_to_use.strip(),
                "Content-Type": "application/json"
            }
            # Clean special characters like ₹ to avoid mispronunciations
            cleaned_text = text.replace("₹", "रुपये ").replace("Rs.", "रुपये ")

            payload = {
                "text": cleaned_text,
                "language": lang,
                "model": "timbre-v3.0",
                "voice": voice,
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
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post(self.api_url, headers=headers, json=payload)
                    if res.status_code == 200 and len(res.content) > 100:
                        print(f"[GnaniTTS] Successfully synthesized {len(res.content)} bytes from Timbre v3.0")
                        return res.content
                    else:
                        print(f"[GnaniTTS] API returned status {res.status_code}: {res.text}")
            except Exception as e:
                print(f"[GnaniTTS] Error connecting to Timbre TTS API: {e}")

        # Fallback tone if no key provided yet
        return self._generate_fallback_wav(duration_seconds=1.0)

    def _generate_fallback_wav(self, duration_seconds: float = 1.0) -> bytes:
        buf = io.BytesIO()
        sample_rate = 16000
        n_samples = int(sample_rate * duration_seconds)
        with wave.open(buf, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b'\x00\x00' * n_samples)
        return buf.getvalue()

gnani_tts = GnaniTTSService()
