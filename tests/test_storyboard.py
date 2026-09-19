from shorts.config import Settings
from shorts.models import Script, WordTiming
from shorts.storyboard import plan_scenes, segment_words


def words_from(text, per_word=0.4):
    out, t = [], 0.0
    for w in text.split():
        out.append(WordTiming(w, t, t + per_word))
        t += per_word
    return out


def test_segment_prefers_sentence_ends_and_respects_max():
    text = "Раз два три четыре пять шесть семь восемь девять. Десять одиннадцать двенадцать тринадцать. " * 3
    words = words_from(text)  # ~0.4 с на слово, предложения по 3.6 и 1.6 с
    segs = segment_words(words, target=5.5, min_len=3.0, max_len=7.5, total=words[-1].end)
    assert segs[0].start == 0.0
    assert abs(segs[-1].end - words[-1].end) < 1e-6
    for a, b in zip(segs, segs[1:]):
        assert abs(a.end - b.start) < 1e-6  # без дыр
    assert all(s.duration <= 7.5 + 0.41 for s in segs)
    assert all(s.text.rstrip().endswith((".", "!", "?")) or s.duration >= 7.0 for s in segs)


def test_segment_single_long_sentence_is_cut_by_max():
    words = words_from(" ".join(["слово"] * 60))  # 24 с без знаков
    segs = segment_words(words, target=5.5, min_len=3.0, max_len=7.5)
    assert len(segs) >= 3 and max(s.duration for s in segs) <= 7.5 + 0.41


class FakeLLM:
    def __init__(self, n):
        self.n = n
        self.calls = []

    def complete_json(self, system, user, schema, temperature=0.7):
        self.calls.append((system, user))
        return {"scenes": [{"prompt": f"scene {i} slow push-in"} for i in range(self.n)]}


def test_plan_scenes_pads_missing():
    script = Script(title="T", hook="h", body="b", cta="c", description="d", tags=[])
    segs = segment_words(words_from("Один два три. Четыре пять шесть. Семь восемь девять."), min_len=0.5, max_len=1.3)
    llm = FakeLLM(len(segs) - 1)
    prompts = plan_scenes(llm, script, segs, Settings(_env_file=None))
    assert len(prompts) == len(segs)
    assert prompts[-1] == prompts[-2]
    assert f"exactly {len(segs)} prompts" in llm.calls[0][0]
    assert "cinematic realistic" in llm.calls[0][0]
