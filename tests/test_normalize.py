from shorts.align import align_script_to_timings
from shorts.models import WordTiming
from shorts.tts.normalize import normalize_for_tts


def test_known_and_spelled():
    assert normalize_for_tts("ИИ решил задачу.") == "искусственный интеллект решил задачу."
    assert normalize_for_tts("Учёные из НАСА и МФТИ") == "Учёные из наса и эм-эф-тэ-и"
    assert normalize_for_tts("(GPS) работает, а ЭКГ нет!") == "(джи-пи-эс) работает, а э-ка-гэ нет!"
    assert normalize_for_tts("Google и YouTube") == "гугл и ютуб"


def test_normal_words_untouched():
    assert normalize_for_tts("Кофе по утрам. Вот что это значит.") == "Кофе по утрам. Вот что это значит."
    assert normalize_for_tts("Я и он") == "Я и он"  # однобуквенные не трогаем


def test_alignment_spreads_expanded_abbreviation():
    script = ["Сегодня", "ИИ", "решил", "задачу."]
    heard = [
        WordTiming("сегодня", 0.0, 0.5),
        WordTiming("искусственный", 0.5, 1.1),
        WordTiming("интеллект", 1.1, 1.6),
        WordTiming("решил", 1.6, 2.0),
        WordTiming("задачу", 2.0, 2.5),
    ]
    out = align_script_to_timings(script, heard, 2.6)
    assert [w.word for w in out] == script
    assert out[1].start == 0.5 and abs(out[1].end - 1.6) < 1e-6
    assert out[2].start == 1.6
