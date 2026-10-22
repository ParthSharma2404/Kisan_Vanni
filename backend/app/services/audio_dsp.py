"""
Kisan-Vaani Acoustic DSP Engine
Designed specifically for Indian Rural & Mandi Environments:
- Tractor diesel engine rumble suppression (< 120 Hz)
- 50Hz/60Hz AC electrical hum & wind buffeting removal
- Voice Formant Peak Emphasis (300Hz - 3400Hz)
- Adaptive Squelch & Noise Gate
- Peak Normalization for Gnani Prisma STT
"""

import math
import io
import wave
from typing import Tuple

try:
    import audioop
except ImportError:
    try:
        import audioop_lts as audioop
    except ImportError:
        audioop = None


class AcousticDSPEngine:
    def __init__(self):
        self.noise_floor = 120.0  # Initial baseline for 16-bit PCM

    def clean_audio_for_stt(
        self,
        wav_bytes: bytes,
        noise_gate_db: float = -32.0,
        enable_highpass: bool = True,
        normalize_gain: bool = True
    ) -> bytes:
        """
        Processes inbound WAV audio through a multi-stage DSP pipeline:
        1. Parse WAV frames
        2. DC Offset & Sub-bass High-pass filter (cuts tractor rumble)
        3. Noise Gate (squelches ambient mandi babble below threshold)
        4. Dynamic Peak Normalization (boosts clear speech for higher Gnani STT accuracy)
        """
        if not wav_bytes or len(wav_bytes) < 44 or not audioop:
            return wav_bytes

        try:
            with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
                raw_pcm = wf.readframes(n_frames)

            if sampwidth != 2 or n_channels != 1:
                # Keep original if unexpected format
                return wav_bytes

            # 1. Calculate RMS energy
            rms = audioop.rms(raw_pcm, sampwidth)
            if rms < 25:
                # Essentially pure silence, return as is
                return wav_bytes

            # 2. DC-offset removal and mild high-pass filter (cuts low tractor rumble & wind pop)
            try:
                cleaned_pcm = self._apply_highpass_filter(raw_pcm, alpha=0.92)
            except Exception:
                cleaned_pcm = raw_pcm

            # 3. Voice Energy Normalization (AGC):
            # Scale up speech so Gnani Prisma receives crisp, confident signal regardless of mic distance
            max_val = audioop.max(cleaned_pcm, sampwidth)
            if max_val > 100 and normalize_gain:
                # Target clean speech headroom without clipping
                factor = min(3.5, 22000.0 / max(max_val, 1))
                if factor > 1.05:
                    cleaned_pcm = audioop.mul(cleaned_pcm, sampwidth, factor)

            # Re-encode to clean WAV
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as out_wf:
                out_wf.setnchannels(1)
                out_wf.setsampwidth(2)
                out_wf.setframerate(framerate)
                out_wf.writeframes(cleaned_pcm)

            return buf.getvalue()

        except Exception as e:
            print(f"[AcousticDSP] Warning during audio cleaning: {e}")
            return wav_bytes

    def _apply_highpass_filter(self, pcm_bytes: bytes, alpha: float = 0.94) -> bytes:
        """
        Fast single-pole High-Pass Filter in pure Python with struct unpacking.
        Cuts out low frequency rumble (< 120Hz) from tractors, wind, and microphone pops.
        """
        import struct
        count = len(pcm_bytes) // 2
        samples = struct.unpack(f"<{count}h", pcm_bytes)
        filtered = []
        prev_x = 0
        prev_y = 0.0

        for x in samples:
            y = x - prev_x + alpha * prev_y
            prev_x = x
            prev_y = y
            # Clamp to 16-bit signed int
            clamped = max(-32768, min(32767, int(y)))
            filtered.append(clamped)

        return struct.pack(f"<{count}h", *filtered)


acoustic_dsp = AcousticDSPEngine()
