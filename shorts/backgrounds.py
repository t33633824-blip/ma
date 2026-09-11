"""Фоновые видео: сгенерировать «залипательную» анимацию или скачать бесплатные стоковые ролики."""
from __future__ import annotations

import colorsys
import logging
import math
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw

from .ffmpeg import ffmpeg_exe

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- генератор


@dataclass
class Ball:
    x: float
    y: float
    vx: float
    vy: float
    r: float
    hue: float


def _hsv(h: float, s: float = 0.9, v: float = 1.0) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def generate_bouncing(
    out_path: str,
    seconds: float = 180.0,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    seed: int | None = None,
    balls: int = 3,
) -> str:
    """Шарики скачут внутри кольца, растут и меняют цвет при каждом ударе, оставляют тающий след.

    Классический «залипательный» фон без чужих прав: всё нарисовано кодом.
    """
    rng = random.Random(seed)
    cx, cy = width / 2, height / 2
    ring_r = min(width, height) * 0.42
    gravity = 0.55
    trail = 0.93  # доля яркости следа, остающаяся на следующем кадре

    objs = [
        Ball(
            x=cx + rng.uniform(-ring_r * 0.4, ring_r * 0.4),
            y=cy + rng.uniform(-ring_r * 0.4, 0),
            vx=rng.uniform(-6, 6),
            vy=rng.uniform(-3, 3),
            r=rng.uniform(14, 22),
            hue=rng.random(),
        )
        for _ in range(balls)
    ]
    ring_hue = rng.random()
    canvas = np.zeros((height, width, 3), dtype=np.float32)

    cmd = [
        ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", out_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    total_frames = int(seconds * fps)
    max_r = ring_r * 0.28
    try:
        for frame in range(total_frames):
            canvas *= trail
            img = Image.fromarray(canvas.astype(np.uint8))
            draw = ImageDraw.Draw(img)
            ring_hue += 0.0007
            draw.ellipse(
                (cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r),
                outline=_hsv(ring_hue, 0.6, 1.0), width=8,
            )
            for b in objs:
                b.vy += gravity
                b.x += b.vx
                b.y += b.vy
                dx, dy = b.x - cx, b.y - cy
                dist = math.hypot(dx, dy) or 1e-6
                if dist + b.r >= ring_r:
                    nx, ny = dx / dist, dy / dist
                    dot = b.vx * nx + b.vy * ny
                    b.vx -= 2 * dot * nx
                    b.vy -= 2 * dot * ny
                    b.vx *= 1.002
                    b.vy *= 1.002
                    overlap = dist + b.r - ring_r
                    b.x -= nx * overlap
                    b.y -= ny * overlap
                    b.hue += 0.07
                    if b.r < max_r:
                        b.r += 1.2
                    else:
                        b.r = rng.uniform(14, 22)  # шарик «лопается» и растёт заново
                draw.ellipse((b.x - b.r, b.y - b.r, b.x + b.r, b.y + b.r), fill=_hsv(b.hue))
            frame_arr = np.asarray(img, dtype=np.float32)
            canvas = np.maximum(canvas, frame_arr)
            proc.stdin.write(canvas.astype(np.uint8).tobytes())
            if frame % (fps * 30) == 0 and frame:
                log.info("Генерация фона: %d/%d с", frame // fps, int(seconds))
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg не смог записать сгенерированный фон")
    return out_path


# ---------------------------------------------------------------- стоковые видео (Pexels)

PEXELS_URL = "https://api.pexels.com/videos/search"


def pexels_search(query: str, api_key: str, per_page: int = 15, page: int = 1, client: httpx.Client | None = None) -> list[dict]:
    """Поиск вертикальных видео на Pexels. Лицензия Pexels разрешает коммерческое использование без указания автора."""
    http = client or httpx.Client(timeout=30.0)
    resp = http.get(
        PEXELS_URL,
        params={"query": query, "orientation": "portrait", "size": "medium", "per_page": per_page, "page": page},
        headers={"Authorization": api_key},
    )
    resp.raise_for_status()
    return resp.json().get("videos", [])


def best_portrait_file(video: dict, min_height: int = 1280) -> dict | None:
    files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("height", 0) >= f.get("width", 0)]
    files = [f for f in files if f.get("height", 0) >= min_height] or files
    if not files:
        return None
    return max(files, key=lambda f: f.get("height", 0))


def fetch_pexels(query: str, count: int, api_key: str, out_dir: Path, min_seconds: int = 15, client: httpx.Client | None = None) -> list[Path]:
    """Скачивает до count вертикальных роликов по запросу в out_dir. Уже скачанные пропускает."""
    if not api_key:
        raise ValueError("Нужен PEXELS_API_KEY: бесплатно на https://www.pexels.com/api/")
    out_dir.mkdir(parents=True, exist_ok=True)
    http = client or httpx.Client(timeout=120.0, follow_redirects=True)
    saved: list[Path] = []
    page = 1
    while len(saved) < count and page <= 5:
        videos = pexels_search(query, api_key, per_page=15, page=page, client=http)
        if not videos:
            break
        for v in videos:
            if len(saved) >= count:
                break
            if v.get("duration", 0) < min_seconds:
                continue
            f = best_portrait_file(v)
            if not f:
                continue
            dest = out_dir / f"pexels-{v['id']}.mp4"
            if dest.exists():
                saved.append(dest)
                continue
            log.info("Скачиваю %s (%sx%s, %s с, автор %s)", dest.name, f.get("width"), f.get("height"), v.get("duration"), v.get("user", {}).get("name"))
            with http.stream("GET", f["link"]) as r:
                r.raise_for_status()
                with open(dest, "wb") as fh:
                    for chunk in r.iter_bytes():
                        fh.write(chunk)
            saved.append(dest)
        page += 1
    return saved
