"""Работа со звуком: сжатие длинных пауз в озвучке с пересчётом таймингов слов."""
from __future__ import annotations

import wave
from dataclasses import dataclass

import numpy as np

from .models import WordTiming


@dataclass
class Cut:
    start: float  # где в исходном аудио начинается вырезанный кусок
    length: float  # сколько секунд удалено


def read_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1).astype(np.int16)
    return data, sr


def write_wav(path: str, data: np.ndarray, sr: int) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.astype(np.int16).tobytes())


def find_silences(data: np.ndarray, sr: int, threshold_db: float = -38.0, frame_ms: int = 10) -> list[tuple[float, float]]:
    """Интервалы тишины (сек) по RMS в окнах frame_ms."""
    frame = max(1, int(sr * frame_ms / 1000))
    n = len(data) // frame
    if n == 0:
        return []
    x = data[: n * frame].astype(np.float32).reshape(n, frame) / 32768.0
    rms = np.sqrt((x**2).mean(axis=1)) + 1e-9
    db = 20 * np.log10(rms)
    quiet = db < threshold_db
    out: list[tuple[float, float]] = []
    i = 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            out.append((i * frame / sr, j * frame / sr))
            i = j
        else:
            i += 1
    return out


def compress_pauses(wav_in: str, wav_out: str, max_pause: float = 0.35, threshold_db: float = -38.0, keep_edges: float = 0.15) -> list[Cut]:
    """Укорачивает каждую паузу длиннее max_pause до max_pause. Возвращает список вырезанных кусков
    в координатах исходного файла, чтобы пересчитать тайминги слов."""
    data, sr = read_wav(wav_in)
    cuts: list[Cut] = []
    keep_mask = np.ones(len(data), dtype=bool)
    for s, e in find_silences(data, sr, threshold_db):
        length = e - s
        if length <= max_pause:
            continue
        # оставляем max_pause: часть в начале, часть в конце, вырезаем середину
        head = min(keep_edges, max_pause / 2)
        tail = max_pause - head
        cut_s = s + head
        cut_e = e - tail
        keep_mask[int(cut_s * sr) : int(cut_e * sr)] = False
        cuts.append(Cut(start=cut_s, length=cut_e - cut_s))
    write_wav(wav_out, data[keep_mask], sr)
    return cuts


def remap_time(t: float, cuts: list[Cut]) -> float:
    """Переводит момент времени из исходного аудио в сжатое."""
    shift = 0.0
    for c in cuts:
        if t >= c.start + c.length:
            shift += c.length
        elif t > c.start:
            shift += t - c.start  # момент внутри вырезанного куска схлопывается к его началу
    return max(0.0, t - shift)


def remap_words(words: list[WordTiming], cuts: list[Cut]) -> list[WordTiming]:
    out = []
    for w in words:
        s = remap_time(w.start, cuts)
        e = max(remap_time(w.end, cuts), s + 0.05)
        out.append(WordTiming(w.word, s, e))
    return out
