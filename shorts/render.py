from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .background import BackgroundClip
from .ffmpeg import ffmpeg_exe

log = logging.getLogger(__name__)


def render_video(
    bg: BackgroundClip,
    voice_wav: str,
    subs_ass: str,
    out_mp4: str,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    tail_seconds: float = 0.6,
) -> None:
    """Собирает вертикальный ролик: фон под 9:16, озвучка, субтитры. Звук фона отключён."""
    total = bg.duration + tail_seconds
    subs_ass = str(Path(subs_ass).resolve())
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps},"
        f"ass=filename='{_escape_filter_path(subs_ass)}'"
    )
    cmd = [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error"]
    if bg.path:
        cmd += ["-ss", f"{bg.start:.2f}", "-t", f"{total:.2f}", "-i", bg.path]
    else:
        cmd += ["-f", "lavfi", "-t", f"{total:.2f}", "-i", f"testsrc2=size={width}x{height}:rate={fps}"]
    cmd += [
        "-i", voice_wav,
        "-filter_complex", f"[0:v]{vf}[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
        "-t", f"{total:.2f}", "-movflags", "+faststart",
        out_mp4,
    ]
    log.info("ffmpeg: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg завершился с ошибкой:\n{proc.stderr[-2000:]}")


def _escape_filter_path(path: str) -> str:
    # внутри filtergraph спецсимволы экранируются: \ : '
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
