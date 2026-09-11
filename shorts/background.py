from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from pathlib import Path

from .ffmpeg import media_duration

log = logging.getLogger(__name__)
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


@dataclass
class BackgroundClip:
    path: str | None  # None = сгенерировать заглушку
    start: float
    duration: float


def list_gameplay(gameplay_dir: Path) -> list[Path]:
    if not gameplay_dir.exists():
        return []
    return sorted(p for p in gameplay_dir.iterdir() if p.suffix.lower() in VIDEO_EXT)


def pick_background(gameplay_dir: Path, need_seconds: float, forced: str | None = None, rng: random.Random | None = None) -> BackgroundClip:
    """Случайный файл и случайный фрагмент нужной длины. Без файлов вернёт заглушку."""
    rng = rng or random.Random()
    files = [Path(forced)] if forced else list_gameplay(gameplay_dir)
    if not files:
        log.warning("В %s нет видео, фон будет сгенерирован. Положи туда свой геймплей.", gameplay_dir)
        return BackgroundClip(path=None, start=0.0, duration=need_seconds)
    path = rng.choice(files)
    total = media_duration(str(path))
    need = need_seconds + 1.0  # запас на хвост ролика
    if total <= need:
        log.warning("Фон %s короче ролика (%.0f c < %.0f c), будет зациклен", path.name, total, need)
        return BackgroundClip(path=str(path), start=0.0, duration=need_seconds)
    start = rng.uniform(0.0, total - need)
    return BackgroundClip(path=str(path), start=round(start, 2), duration=need_seconds)
