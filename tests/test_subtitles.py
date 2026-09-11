from shorts.models import WordTiming
from shorts.subtitles import ass_time, build_ass, chunk_words, escape_ass


def w(text, s, e):
    return WordTiming(text, s, e)


def test_ass_time_format():
    assert ass_time(0) == "0:00:00.00"
    assert ass_time(65.5) == "0:01:05.50"
    assert ass_time(3661.234) == "1:01:01.23"
    assert ass_time(-1) == "0:00:00.00"


def test_chunk_by_count_and_sentence_end():
    words = [w("Кофе", 0, 1), w("бодрит.", 1, 2), w("А", 2, 3), w("чай", 3, 4), w("нет", 4, 5), w("совсем", 5, 6)]
    chunks = chunk_words(words, 3)
    assert [[x.word for x in c] for c in chunks] == [["Кофе", "бодрит."], ["А", "чай", "нет"], ["совсем"]]


def test_build_ass_highlights_each_word_once():
    words = [w("Один", 0.0, 0.5), w("два", 0.5, 1.0), w("три", 1.0, 1.5)]
    ass = build_ass(words, per_line=3)
    dialogues = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogues) == 3
    assert "ОДИН" in dialogues[0] and dialogues[0].count("\\c&H0000E5FF") == 1
    assert dialogues[0].split(",")[1] == "0:00:00.00" and dialogues[0].split(",")[2] == "0:00:00.50"
    assert "PlayResX: 1080" in ass


def test_escape_braces():
    assert escape_ass("a{b}c\\") == "a(b)c\\\\"
