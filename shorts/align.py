from __future__ import annotations

import re
from difflib import SequenceMatcher

from .models import WordTiming

_PUNCT = re.compile(r"[^\w]+", re.UNICODE)


def normalize(word: str) -> str:
    return _PUNCT.sub("", word).lower().replace("ё", "е")


def split_words(text: str) -> list[str]:
    return [w for w in text.split() if normalize(w)]


def transcribe_words(wav_path: str, model_name: str, download_root: str) -> list[WordTiming]:
    """Локальное распознавание через faster-whisper с таймингами по словам."""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8", download_root=download_root)
    segments, _ = model.transcribe(wav_path, language="ru", word_timestamps=True, beam_size=1)
    return [WordTiming(w.word.strip(), float(w.start), float(w.end)) for seg in segments for w in seg.words or []]


def align_script_to_timings(script_words: list[str], heard: list[WordTiming], total_duration: float) -> list[WordTiming]:
    """Сопоставляет слова сценария (правильный текст) с тем, что услышал whisper (правильное время).

    Совпавшие слова берут время из распознавания, пропущенные равномерно распределяются
    между соседями. На выходе ровно len(script_words) элементов в исходном порядке.
    """
    if not script_words:
        return []
    if not heard:
        return _spread(script_words, 0.0, total_duration)

    a = [normalize(w) for w in script_words]
    b = [normalize(w.word) for w in heard]
    matcher = SequenceMatcher(a=a, b=b, autojunk=False)

    starts: list[float | None] = [None] * len(script_words)
    ends: list[float | None] = [None] * len(script_words)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                starts[i1 + k] = heard[j1 + k].start
                ends[i1 + k] = heard[j1 + k].end
        elif tag == "replace" and (i2 - i1) == (j2 - j1):
            # одинаковое число слов, whisper просто расслышал иначе: доверяем времени
            for k in range(i2 - i1):
                starts[i1 + k] = heard[j1 + k].start
                ends[i1 + k] = heard[j1 + k].end

    result: list[WordTiming] = []
    i = 0
    n = len(script_words)
    while i < n:
        if starts[i] is not None:
            result.append(WordTiming(script_words[i], starts[i], ends[i]))  # type: ignore[arg-type]
            i += 1
            continue
        # пробел неизвестных слов [i, j)
        j = i
        while j < n and starts[j] is None:
            j += 1
        gap_start = result[-1].end if result else 0.0
        gap_end = starts[j] if j < n else total_duration  # type: ignore[assignment]
        if gap_end <= gap_start:
            gap_end = gap_start + 0.25 * (j - i)
        result.extend(_spread(script_words[i:j], gap_start, gap_end))
        i = j

    # монотонность: конец не раньше начала, следующее не раньше предыдущего
    last_end = 0.0
    for w in result:
        w.start = max(w.start, last_end)
        w.end = max(w.end, w.start + 0.05)
        last_end = w.end
    return result


def _spread(words: list[str], start: float, end: float) -> list[WordTiming]:
    if not words:
        return []
    step = (end - start) / len(words)
    return [WordTiming(w, start + k * step, start + (k + 1) * step) for k, w in enumerate(words)]
