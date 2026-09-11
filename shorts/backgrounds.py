"""Фоновые видео: сгенерировать «залипательную» анимацию или скачать бесплатные стоковые ролики.

Сцены генератора:
- bounce: шарики скачут в кольце, растут и меняют цвет при ударе;
- split:  один шарик при каждом ударе рождает ещё один, пока экран не заполнится, потом всё начинается заново;
- flow:   сотни частиц текут по невидимому полю, оставляя светящиеся следы.
"""
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
from PIL import Image, ImageDraw, ImageFilter

from .ffmpeg import ffmpeg_exe

log = logging.getLogger(__name__)

SCENES = ("bounce", "split", "flow")


# ---------------------------------------------------------------- общая часть


@dataclass
class Ball:
    x: float
    y: float
    vx: float
    vy: float
    r: float
    hue: float
    grow: float = 1.0  # +1 растёт при ударах, -1 плавно уменьшается


def _hsv(h: float, s: float = 0.9, v: float = 1.0) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def _gradient_bg(width: int, height: int, hue: float) -> np.ndarray:
    """Тёмный вертикальный градиент вместо чёрного: картинка выглядит дороже."""
    top = np.array(_hsv(hue, 0.6, 0.16), dtype=np.float32)
    bottom = np.array(_hsv(hue + 0.08, 0.7, 0.05), dtype=np.float32)
    t = np.linspace(0, 1, height, dtype=np.float32)[:, None, None]
    return top * (1 - t) + bottom * t + np.zeros((height, width, 3), dtype=np.float32)


class _Encoder:
    def __init__(self, out_path: str, width: int, height: int, fps: int):
        cmd = [
            ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", out_path,
        ]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, frame: np.ndarray) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())

    def close(self) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.close()
        self.proc.wait()
        if self.proc.returncode != 0:
            raise RuntimeError("ffmpeg не смог записать сгенерированный фон")


def _glow(img: Image.Image, radius: int = 18) -> np.ndarray:
    """Слой свечения: размытая копия, которую складываем с картинкой."""
    return np.asarray(img.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) * 0.9


def _bounce_in_ring(b: Ball, cx: float, cy: float, ring_r: float) -> bool:
    dx, dy = b.x - cx, b.y - cy
    dist = math.hypot(dx, dy) or 1e-6
    if dist + b.r < ring_r:
        return False
    nx, ny = dx / dist, dy / dist
    dot = b.vx * nx + b.vy * ny
    b.vx -= 2 * dot * nx
    b.vy -= 2 * dot * ny
    overlap = dist + b.r - ring_r
    b.x -= nx * overlap
    b.y -= ny * overlap
    return True


# ---------------------------------------------------------------- сцены


def _scene_bounce(enc: _Encoder, rng: random.Random, seconds: float, width: int, height: int, fps: int, balls: int) -> None:
    cx, cy = width / 2, height / 2
    ring_r = min(width, height) * 0.44
    gravity = 0.55
    objs = [
        Ball(cx + rng.uniform(-ring_r * 0.4, ring_r * 0.4), cy + rng.uniform(-ring_r * 0.4, 0), rng.uniform(-6, 6), rng.uniform(-3, 3), rng.uniform(16, 24), rng.random())
        for _ in range(balls)
    ]
    ring_hue = rng.random()
    bg = _gradient_bg(width, height, ring_hue + 0.5)
    trail = np.zeros((height, width, 3), dtype=np.float32)
    max_r = ring_r * 0.28
    for frame in range(int(seconds * fps)):
        trail *= 0.92
        layer = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(layer)
        ring_hue += 0.0007
        draw.ellipse((cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r), outline=_hsv(ring_hue, 0.6, 1.0), width=10)
        for b in objs:
            b.vy += gravity
            b.x += b.vx
            b.y += b.vy
            if _bounce_in_ring(b, cx, cy, ring_r):
                b.vx *= 1.002
                b.vy *= 1.002
                b.hue += 0.07
                if b.grow > 0:
                    b.r += 1.4
                    if b.r >= max_r:
                        b.grow = -1.0  # дорос: дальше плавно сдувается, без скачка
            if b.grow < 0:
                b.r -= 0.12
                if b.r <= 18:
                    b.grow = 1.0
            speed = math.hypot(b.vx, b.vy)
            if speed > 26:  # не даём разогнаться до мельтешения
                b.vx *= 26 / speed
                b.vy *= 26 / speed
            draw.ellipse((b.x - b.r, b.y - b.r, b.x + b.r, b.y + b.r), fill=_hsv(b.hue))
        arr = np.asarray(layer, dtype=np.float32)
        trail = np.maximum(trail, arr)
        enc.write(bg + trail + _glow(layer))
        _progress(frame, fps, seconds)


def _scene_split(enc: _Encoder, rng: random.Random, seconds: float, width: int, height: int, fps: int, max_balls: int = 60) -> None:
    cx, cy = width / 2, height / 2
    ring_r = min(width, height) * 0.44
    gravity = 0.5
    base_hue = rng.random()
    bg = _gradient_bg(width, height, base_hue + 0.5)
    trail = np.zeros((height, width, 3), dtype=np.float32)

    objs = [Ball(cx, cy - ring_r * 0.3, rng.uniform(-4, 4), 0.0, 26, base_hue)]
    shrink = 0.03  # каждый шарик медленно тает; исчезнув, освобождает место новым
    for frame in range(int(seconds * fps)):
        trail *= 0.9
        layer = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(layer)
        draw.ellipse((cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r), outline=_hsv(base_hue + frame * 0.0005, 0.5, 1.0), width=10)
        spawned: list[Ball] = []
        alive: list[Ball] = []
        for b in objs:
            b.vy += gravity
            b.x += b.vx
            b.y += b.vy
            speed = math.hypot(b.vx, b.vy)
            if speed > 24:
                b.vx *= 24 / speed
                b.vy *= 24 / speed
            if _bounce_in_ring(b, cx, cy, ring_r) and len(objs) + len(spawned) < max_balls:
                ang = rng.uniform(0, math.tau)
                spd = speed * rng.uniform(0.7, 1.1)
                spawned.append(Ball(b.x, b.y, math.cos(ang) * spd, math.sin(ang) * spd, max(14, b.r * 0.95), b.hue + rng.uniform(0.05, 0.15)))
            b.r -= shrink
            if b.r > 4:
                alive.append(b)
                draw.ellipse((b.x - b.r, b.y - b.r, b.x + b.r, b.y + b.r), fill=_hsv(b.hue))
        objs = alive + spawned
        if not objs:  # всё растаяло, тихо запускаем новый шарик
            objs = [Ball(cx, cy - ring_r * 0.3, rng.uniform(-4, 4), 0.0, 26, base_hue + frame * 0.0005)]
        arr = np.asarray(layer, dtype=np.float32)
        trail = np.maximum(trail, arr)
        enc.write(bg + trail + _glow(layer, 14))
        _progress(frame, fps, seconds)


def _scene_flow(enc: _Encoder, rng: random.Random, seconds: float, width: int, height: int, fps: int, particles: int = 700) -> None:
    hue0 = rng.random()
    bg = _gradient_bg(width, height, hue0 + 0.5)
    trail = np.zeros((height, width, 3), dtype=np.float32)
    px = np.array([rng.uniform(0, width) for _ in range(particles)], dtype=np.float32)
    py = np.array([rng.uniform(0, height) for _ in range(particles)], dtype=np.float32)
    phase = [rng.uniform(0, math.tau) for _ in range(4)]
    k = [rng.uniform(0.002, 0.005) for _ in range(4)]
    speed = 3.2
    for frame in range(int(seconds * fps)):
        t = frame / fps
        # плавно меняющееся поле направлений из суммы синусов
        ang = (
            np.sin(px * k[0] + phase[0] + t * 0.25)
            + np.cos(py * k[1] + phase[1] - t * 0.2)
            + np.sin((px + py) * k[2] + phase[2] + t * 0.15)
        ) * math.pi
        px += np.cos(ang) * speed
        py += np.sin(ang) * speed
        out = (px < 0) | (px >= width) | (py < 0) | (py >= height)
        n_out = int(out.sum())
        if n_out:
            px[out] = np.array([rng.uniform(0, width) for _ in range(n_out)], dtype=np.float32)
            py[out] = np.array([rng.uniform(0, height) for _ in range(n_out)], dtype=np.float32)
        trail *= 0.955
        layer = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(layer)
        hue = hue0 + t * 0.02
        for i in range(particles):
            h = hue + (py[i] / height) * 0.25
            x, y = float(px[i]), float(py[i])
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=_hsv(h, 0.8, 1.0))
        arr = np.asarray(layer, dtype=np.float32)
        trail = np.maximum(trail, arr)
        enc.write(bg + trail + _glow(layer, 10))
        _progress(frame, fps, seconds)


def _progress(frame: int, fps: int, seconds: float) -> None:
    if frame and frame % (fps * 30) == 0:
        log.info("Генерация фона: %d/%d с", frame // fps, int(seconds))


def generate_background(
    out_path: str,
    scene: str = "random",
    seconds: float = 180.0,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    seed: int | None = None,
    balls: int = 3,
) -> str:
    rng = random.Random(seed)
    if scene == "random":
        scene = rng.choice(SCENES)
    if scene not in SCENES:
        raise ValueError(f"Неизвестная сцена {scene}, доступны: {', '.join(SCENES)}")
    log.info("Сцена: %s", scene)
    enc = _Encoder(out_path, width, height, fps)
    try:
        if scene == "bounce":
            _scene_bounce(enc, rng, seconds, width, height, fps, balls)
        elif scene == "split":
            _scene_split(enc, rng, seconds, width, height, fps)
        else:
            _scene_flow(enc, rng, seconds, width, height, fps)
    finally:
        enc.close()
    return out_path


def generate_bouncing(out_path: str, seconds: float = 180.0, width: int = 1080, height: int = 1920, fps: int = 30, seed: int | None = None, balls: int = 3) -> str:
    """Совместимость со старым именем."""
    return generate_background(out_path, "bounce", seconds, width, height, fps, seed, balls)


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
