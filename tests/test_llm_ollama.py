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
