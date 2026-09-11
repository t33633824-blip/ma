from __future__ import annotations

import wave
from pathlib import Path

from ..models import TTSResult


class PiperTTS:
    """Локальная озвучка через Piper. Голос скачивается один раз:
    python -m piper.download_voices --download-dir models/piper ru_RU-irina-medium
    """

    def __init__(self, voices_dir: Path, voice: str, length_scale: float = 1.0, noise_w: float = 0.8):
        self.voices_dir = Path(voices_dir)
        self.voice_name = voice
        self.length_scale = length_scale
        self.noise_w = noise_w
        self._voice = None

    def _load(self):
        if self._voice is None:
            from piper import PiperVoice

            model_path = self.voices_dir / f"{self.voice_name}.onnx"
            if not model_path.exists():
                self.voices_dir.mkdir(parents=True, exist_ok=True)
                from piper.download_voices import download_voice

                download_voice(self.voice_name, self.voices_dir)
            self._voice = PiperVoice.load(str(model_path))
        return self._voice

    def synthesize(self, text: str, wav_path: str) -> TTSResult:
        from piper import SynthesisConfig

        voice = self._load()
        cfg = SynthesisConfig(length_scale=self.length_scale, noise_w_scale=self.noise_w)
        chunks = list(voice.synthesize(text, cfg))
        if not chunks:
            raise RuntimeError("Piper не вернул аудио")
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(chunks[0].sample_channels)
            w.setsampwidth(chunks[0].sample_width)
            w.setframerate(chunks[0].sample_rate)
            for chunk in chunks:
                w.writeframes(chunk.audio_int16_bytes)
        # Piper не отдаёт тайминги слов для русских голосов, их даст whisper.
        return TTSResult(wav_path=wav_path, words=[])
