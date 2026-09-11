from __future__ import annotations

from ..config import Settings
from .base import TTS


def get_tts(settings: Settings) -> TTS:
    if settings.tts_provider == "piper":
        from .piper_tts import PiperTTS

        return PiperTTS(settings.piper_dir, settings.piper_voice)
    if settings.tts_provider == "edge":
        from .edge_tts_ import EdgeTTS

        return EdgeTTS(settings.edge_voice)
    if settings.tts_provider == "elevenlabs":
        from .elevenlabs_tts import ElevenLabsTTS

        return ElevenLabsTTS(settings.elevenlabs_api_key, settings.elevenlabs_voice_id)
    raise ValueError(f"Неизвестный TTS_PROVIDER: {settings.tts_provider}")
