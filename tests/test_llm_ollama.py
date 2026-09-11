import json

import httpx

from shorts.config import Settings
from shorts.llm.ollama_llm import OllamaLLM
from shorts.models import SourceDoc

SCRIPT = {
    "title": "Кофе и память",
    "hook": "Кофе меняет память.",
    "body": "Учёные проверили это на людях.",
    "cta": "А вы пьёте кофе утром?",
    "description": "По мотивам статьи.",
    "tags": ["кофе", "наука"],
}


def test_ollama_structured_request_and_parse():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": json.dumps(SCRIPT)}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = OllamaLLM("http://ollama.local:11434/", "qwen2.5:7b", client=client)
    settings = Settings(_env_file=None)
    doc = SourceDoc(url="https://example.com/a", title="Coffee", text="Coffee improves memory, study says.")

    script = llm.generate_script(doc, settings)

    assert script.title == "Кофе и память"
    assert script.narration == "Кофе меняет память. Учёные проверили это на людях. А вы пьёте кофе утром?"
    assert captured["url"] == "http://ollama.local:11434/api/chat"
    body = captured["body"]
    assert body["model"] == "qwen2.5:7b" and body["stream"] is False
    assert body["format"]["type"] == "object" and "hook" in body["format"]["properties"]
    assert "Coffee improves memory" in body["messages"][1]["content"]
    assert "наука и технологии" in body["messages"][0]["content"]


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete_json(self, system, user, schema, temperature=0.7):
        self.calls.append((system, user, temperature))
        return self.replies.pop(0)


def _script(n_words):
    return dict(SCRIPT, body=" ".join(["слово"] * n_words))


def test_write_script_polishes_once_when_length_ok():
    from shorts.llm.base import write_script

    settings = Settings(_env_file=None, target_seconds=50)  # цель 115 слов
    llm = FakeLLM([_script(90), _script(85)])
    doc = SourceDoc(url="u", title="t", text="x")
    out = write_script(llm, doc, settings)
    assert len(llm.calls) == 2
    assert "редактор" in llm.calls[1][0] and llm.calls[1][2] == 0.3
    assert "обязательно сократи" not in llm.calls[1][0]
    assert len(out.body.split()) == 85


def test_write_script_shortens_until_fits():
    from shorts.llm.base import write_script

    settings = Settings(_env_file=None, target_seconds=50)
    llm = FakeLLM([_script(200), _script(170), _script(120)])
    out = write_script(llm, SourceDoc(url="u", title="t", text="x"), settings)
    assert len(llm.calls) == 3
    assert all("обязательно сократи" in c[0] for c in llm.calls[1:])
    assert len(out.body.split()) == 120


def test_write_script_without_polish():
    from shorts.llm.base import write_script

    settings = Settings(_env_file=None, writer_polish=False)
    llm = FakeLLM([_script(300)])
    write_script(llm, SourceDoc(url="u", title="t", text="x"), settings)
    assert len(llm.calls) == 1
