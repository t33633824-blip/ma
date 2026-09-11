from shorts.tts.elevenlabs_tts import chars_to_words


def test_chars_to_words():
    chars = list("да нет")
    starts = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    ends = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    words = chars_to_words(chars, starts, ends)
    assert [(w.word, w.start, w.end) for w in words] == [("да", 0.0, 0.2), ("нет", 0.3, 0.6)]
