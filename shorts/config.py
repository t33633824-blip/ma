from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все настройки читаются из .env или переменных окружения."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Куратор: ищет и отбирает темы (по умолчанию Claude с веб-поиском)
    curator_provider: Literal["anthropic", "ollama"] = "anthropic"
    curator_model: str = "claude-opus-5"
    curator_web_search: bool = True
    curator_days: int = 7
    curator_picks: int = 5
    feeds_file: Path = Path("feeds.txt")
    queue_file: Path = Path("queue.json")

    # Автор: пишет сценарий, описание, теги (по умолчанию локальная модель)
    writer_provider: Literal["ollama", "anthropic"] = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"
    writer_polish: bool = True  # второй проход той же модели: грамматика, живость, хронометраж

    # TTS
    tts_provider: Literal["piper", "edge", "elevenlabs", "yandex"] = "piper"
    piper_voice: str = "ru_RU-irina-medium"
    piper_dir: Path = Path("models/piper")
    piper_length_scale: float = 0.92  # <1 быстрее и бодрее, >1 медленнее
    piper_noise_w: float = 0.9  # больше вариативности длительностей = менее монотонно
    edge_voice: str = "ru-RU-SvetlanaNeural"
    edge_rate: str = "+10%"
    edge_pitch: str = "+0Hz"

    # Паузы: всё длиннее max сжимается до max секунд
    pause_max_seconds: float = 0.3
    pause_threshold_db: float = -38.0
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_model: str = "eleven_multilingual_v2"
    elevenlabs_stability: float = 0.45
    elevenlabs_similarity: float = 0.8
    elevenlabs_style: float = 0.3
    elevenlabs_speed: float = 1.05
    yandex_api_key: str = ""
    yandex_voice: str = "marina"
    yandex_emotion: str = ""
    yandex_speed: float = 1.05

    # Alignment
    whisper_model: str = "small"
    whisper_dir: Path = Path("models/whisper")

    # Video
    gameplay_dir: Path = Path("assets/gameplay")
    pexels_api_key: str = ""
    out_dir: Path = Path("out")
    video_width: int = 1080
    video_height: int = 1920
    subtitle_font: str = "DejaVu Sans"
    subtitle_words_per_line: int = 3

    # Channel
    channel_topic: str = "наука и технологии"
    channel_style: str = "живой, простой, без канцелярита, как рассказ другу"
    target_seconds: int = 50


def load_settings() -> Settings:
    return Settings()
