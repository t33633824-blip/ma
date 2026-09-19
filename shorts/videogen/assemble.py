"""Склейка сгенерированных клипов в один фоновый ролик точной длины под озвучку."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from ..ffmpeg import ffmpeg_exe


def fit_clip(src: str, dst: str, duration: float, width: int, height: int, fps: int) -> None:
    """Масштабирует под кадр, при нехватке длины держит последний кадр, лишнее обрезает."""
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps={fps},"
        f"tpad=stop_mode=clone:stop_duration={duration + 1:.3f},trim=duration={duration:.3f},setpts=PTS-STARTPTS"
    )
    cmd = [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-i", src, "-an", "-vf", vf,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", dst]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg fit_clip: {proc.stderr[-800:]}")


def assemble_clips(clips: list[tuple[str, float]], out_path: str, width: int, height: int, fps: int = 30) -> str:
    """clips: [(путь, нужная длительность)]. Возвращает out_path (mp4 без звука)."""
    if not clips:
        raise ValueError("Нет клипов для склейки")
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for i, (src, dur) in enumerate(clips):
            dst = str(Path(tmp) / f"part{i:03d}.mp4")
            fit_clip(src, dst, dur, width, height, fps)
            parts.append(dst)
        lst = Path(tmp) / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
        cmd = [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
               "-c", "copy", out_path]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg concat: {proc.stderr[-800:]}")
    return out_path
