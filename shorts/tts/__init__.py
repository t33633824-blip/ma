from __future__ import annotations

from ..config import Settings
from .base import TTS


def get_tts(settings: Settings) -> TTS:
    if settings.tts_provider == "piper":
        from .piper_tts import PiperTTS

        return PiperTTS(settings.piper_dir, settings.piper_voice, settings.piper_length_scale, settings.piper_noise_w)
    if settings.tts_provider == "edge":
        from .edge_tts_ import EdgeTTS

        return EdgeTTS(settings.edge_voice, settings.edge_rate, settings.edge_pitch)
    if settings.tts_provider == "elevenlabs":
        from .elevenlabs_tts import ElevenLabsTTS

        return ElevenLabsTTS(
            settings.elevenlabs_api_key,
            settings.elevenlabs_voice_id,
            settings.elevenlabs_model,
            settings.elevenlabs_stability,
            settings.elevenlabs_similarity,
            settings.elevenlabs_style,
            settings.elevenlabs_speed,
        )
    if settings.tts_provider == "yandex":
        from .yandex_tts import YandexTTS

        return YandexTTS(settings.yandex_api_key, settings.yandex_voice, settings.yandex_emotion, settings.yandex_speed)
    raise ValueError(f"Неизвестный TTS_PROVIDER: {settings.tts_provider}")
