from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Пути, которые по умолчанию живут внутри DATA_DIR (тяжёлые данные: модели, клипы, ролики)
DATA_RELATIVE_FIELDS = ("out_dir", "gameplay_dir", "clips_dir", "piper_dir", "whisper_dir", "video_models_dir")


class Settings(BaseSettings):
    """Все настройки читаются из .env или переменных окружения."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Куда складывать всё тяжёлое. "." = рядом с кодом. Например отдельный диск: /mnt/gen/shorts-data
    data_dir: Path = Path(".")

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
    background_mode: Literal["gameplay", "generated"] = "gameplay"
    gameplay_dir: Path = Path("assets/gameplay")
    pexels_api_key: str = ""

    # Генерация видео по сценам (BACKGROUND_MODE=generated)
    video_provider: Literal["wan"] = "wan"
    video_model: str = "wan22-5b"  # wan22-5b | wan21-1.3b | wan21-14b
    video_steps: int = 0  # 0 = значение пресета
    video_offload: bool = True
    video_seed: int = 0  # 0 = случайно каждый раз
    video_scene_seconds: float = 5.0  # целевая длина сцены
    video_style: str = "cinematic realistic footage, soft natural light, shallow depth of field, muted colors, film grain"
    video_models_dir: Path = Path("models/video")
    clips_dir: Path = Path("assets/clips")
    out_dir: Path = Path("out")
    video_width: int = 1080
    video_height: int = 1920
    subtitle_font: str = "DejaVu Sans"
    subtitle_words_per_line: int = 3

    # Channel
    channel_topic: str = "наука и технологии"
    channel_style: str = "живой, простой, без канцелярита, как рассказ другу"
    target_seconds: int = 50


    @model_validator(mode="after")
    def _rebase_paths(self):
        """Пути, которые не заданы явно, переносим под DATA_DIR."""
        base = self.data_dir
        if str(base) not in (".", ""):
            for name in DATA_RELATIVE_FIELDS:
                if name not in self.model_fields_set:
                    setattr(self, name, base / getattr(self, name))
        return self

    @property
    def hf_home(self) -> Path:
        return self.data_dir / "models" / "hf"


def load_settings() -> Settings:
    s = Settings()
    # кэш Hugging Face (whisper, токенизаторы) тоже на диск с данными, если пользователь не задал свой
    if str(s.data_dir) not in (".", ""):
        os.environ.setdefault("HF_HOME", str(s.hf_home))
    return s
