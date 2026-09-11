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

    # TTS
    tts_provider: Literal["piper", "edge", "elevenlabs"] = "piper"
    piper_voice: str = "ru_RU-irina-medium"
    piper_dir: Path = Path("models/piper")
    edge_voice: str = "ru-RU-DmitryNeural"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    # Alignment
    whisper_model: str = "small"
    whisper_dir: Path = Path("models/whisper")

    # Video
    gameplay_dir: Path = Path("assets/gameplay")
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
