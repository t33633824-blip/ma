import numpy as np

from shorts.audio import compress_pauses, find_silences, remap_time, remap_words, write_wav
from shorts.models import WordTiming


def make_wav(path, segments, sr=16000):
    """segments: список (секунд, громко?)"""
    parts = []
    rng = np.random.default_rng(0)
    for sec, loud in segments:
        n = int(sec * sr)
        parts.append((rng.normal(0, 6000, n) if loud else np.zeros(n)).astype(np.int16))
    write_wav(str(path), np.concatenate(parts), sr)


def test_find_silences(tmp_path):
    p = tmp_path / "a.wav"
    make_wav(p, [(0.5, True), (1.0, False), (0.5, True)])
    from shorts.audio import read_wav

    data, sr = read_wav(str(p))
    sil = find_silences(data, sr)
    assert len(sil) == 1
    s, e = sil[0]
    assert abs(s - 0.5) < 0.02 and abs(e - 1.5) < 0.02


def test_compress_pauses_and_remap(tmp_path):
    src = tmp_path / "a.wav"
    dst = tmp_path / "b.wav"
    make_wav(src, [(0.5, True), (1.0, False), (0.5, True), (0.2, False), (0.5, True)])
    cuts = compress_pauses(str(src), str(dst), max_pause=0.3)
    assert len(cuts) == 1  # пауза 0.2 с не трогается
    assert abs(cuts[0].length - 0.7) < 0.03
    from shorts.audio import read_wav

    data, sr = read_wav(str(dst))
    assert abs(len(data) / sr - (2.7 - 0.7)) < 0.03

    # слово после паузы сдвигается на длину вырезанного куска, слово до паузы не двигается
    assert remap_time(0.3, cuts) == 0.3
    assert abs(remap_time(1.6, cuts) - (1.6 - cuts[0].length)) < 1e-6
    words = remap_words([WordTiming("до", 0.1, 0.4), WordTiming("после", 1.55, 1.9)], cuts)
    assert words[0].start == 0.1
    assert abs(words[1].start - (1.55 - cuts[0].length)) < 1e-6
    assert words[1].end > words[1].start
