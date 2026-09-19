from __future__ import annotations

from ..config import Settings
from .base import VideoGen


def get_videogen(settings: Settings) -> VideoGen:
    if settings.video_provider == "wan":
        from .wan_local import WanLocal

        return WanLocal(
            preset=settings.video_model,
            steps=settings.video_steps or None,
            offload=settings.video_offload,
            clips_dir=settings.clips_dir,
            models_dir=settings.video_models_dir,
        )
    raise ValueError(f"Неизвестный VIDEO_PROVIDER: {settings.video_provider}")
