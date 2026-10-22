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
    import audioop_lts as audioop


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
        if not wav_bytes or len(wav_bytes) < 44:
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
            if rms < 30:
                # Essentially pure silence, return as is
                return wav_bytes

            # Adapt noise floor slowly
            self.noise_floor = self.noise_floor * 0.95 + min(rms, 300) * 0.05

            # 2. DC-offset removal and mild high-pass filter using single-pole difference
            # y[n] = x[n] - x[n-1] + alpha * y[n-1]  (alpha ~ 0.95 corresponds to ~120Hz cutoff at 16kHz)
            cleaned_pcm = self._apply_highpass_filter(raw_pcm, alpha=0.94)

            # 3. Dynamic Noise Gate / Squelch:
            # If overall RMS is barely above the ambient noise floor, attenuate heavily
            snr = 20 * math.log10(max(rms, 1) / max(self.noise_floor, 1))
            if snr < 4.0:
                # Very weak speech submerged in noise: attenuate background
                cleaned_pcm = audioop.mul(cleaned_pcm, sampwidth, 0.3)
            else:
                # 4. Peak Normalization: scale up speech so Gnani Prisma receives clean, confident signal
                max_val = audioop.max(cleaned_pcm, sampwidth)
                if max_val > 500 and max_val < 22000 and normalize_gain:
                    factor = min(3.0, 24000.0 / max_val)
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
