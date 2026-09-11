from __future__ import annotations

import re
import shutil
import subprocess


def ffmpeg_exe() -> str:
    """Системный ffmpeg, если есть, иначе статический бинарник из imageio-ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def media_duration(path: str) -> float:
    """Длительность файла в секундах. Разбирает вывод ffmpeg -i, чтобы не зависеть от ffprobe."""
    proc = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", path], capture_output=True, text=True)
    m = _DURATION_RE.search(proc.stderr)
    if not m:
        raise RuntimeError(f"Не удалось определить длительность: {path}\n{proc.stderr[-500:]}")
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)
