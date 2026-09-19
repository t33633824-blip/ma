from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol


class VideoGen(Protocol):
    fps: int

    def generate(self, prompt: str, seconds: float, seed: int | None = None) -> Path:
        """Возвращает путь к mp4-клипу длиной примерно seconds секунд. Повторный вызов с тем же промптом берёт кэш."""
        ...


def clip_cache_key(*parts: object) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]
