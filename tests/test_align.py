from shorts.align import align_script_to_timings, normalize, split_words
from shorts.models import WordTiming


def heard(*items):
    return [WordTiming(t, s, e) for t, s, e in items]


def test_normalize_strips_punct_and_yo():
    assert normalize(" Учёные,") == "ученые"
    assert split_words("Раз, два  — три.") == ["Раз,", "два", "—", "три."][:2] + ["три."]


def test_exact_match_takes_timings():
    script = ["Кофе", "бодрит", "утром."]
    h = heard(("кофе", 0.0, 0.4), ("бодрит", 0.4, 0.9), ("утром", 0.9, 1.3))
    out = align_script_to_timings(script, h, 1.5)
    assert [(x.word, x.start, x.end) for x in out] == [("Кофе", 0.0, 0.4), ("бодрит", 0.4, 0.9), ("утром.", 0.9, 1.3)]


def test_missing_words_are_interpolated():
    script = ["один", "два", "три", "четыре", "пять"]
    h = heard(("один", 0.0, 1.0), ("пять", 4.0, 5.0))  # whisper пропустил середину
    out = align_script_to_timings(script, h, 5.0)
    assert [x.word for x in out] == script
    assert out[1].start == 1.0 and out[3].end == 4.0
    assert out[2].start == 2.0 and out[2].end == 3.0


def test_no_heard_words_spreads_evenly():
    out = align_script_to_timings(["а", "б", "в", "г"], [], 8.0)
    assert [(x.start, x.end) for x in out] == [(0, 2), (2, 4), (4, 6), (6, 8)]


def test_monotonic_even_with_bad_input():
    script = ["а", "б", "в"]
    h = heard(("а", 1.0, 2.0), ("б", 0.5, 0.7), ("в", 2.5, 3.0))
    out = align_script_to_timings(script, h, 3.0)
    for prev, cur in zip(out, out[1:]):
        assert cur.start >= prev.end
        assert cur.end > cur.start
