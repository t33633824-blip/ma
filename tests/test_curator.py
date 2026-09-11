import json
from types import SimpleNamespace

import httpx

from shorts.config import Settings
from shorts.curator import AnthropicCurator, OllamaCurator, build_rank_prompts, filter_known
from shorts.feeds import Candidate

CANDS = [
    Candidate(url="https://a.com/1", title="Coffee and memory", summary="Study of 200 adults", source="Sci", published="2026-09-09T10:00:00+00:00"),
    Candidate(url="https://b.com/2", title="Old news", summary="", source="Sci"),
]
CURATION = {
    "picks": [{"url": "https://a.com/1", "title": "Coffee and memory", "reason": "конкретный факт", "hook_idea": "Кофе меняет память", "score": 8}],
    "rejected_note": "Old news без сути",
}


def settings():
    return Settings(_env_file=None, curator_picks=3)


def test_prompts_include_candidates_recent_and_web():
    system, user = build_rank_prompts(CANDS, ["Сделанная тема"], "1. Found thing https://c.com/3", settings())
    assert "не больше 3" in system and "наука и технологии" in system
    assert "Coffee and memory" in user and "https://a.com/1" in user
    assert "- Сделанная тема" in user
    assert "Находки из веб-поиска" in user and "https://c.com/3" in user


def test_filter_known():
    out = filter_known(CANDS, {"https://a.com/1"})
    assert [c.url for c in out] == ["https://b.com/2"]


def test_ollama_curator_ranks():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["format"]["properties"]["picks"]
        return httpx.Response(200, json={"message": {"content": json.dumps(CURATION)}})

    cur = OllamaCurator("http://x", "qwen", client=httpx.Client(transport=httpx.MockTransport(handler)))
    res = cur.curate(CANDS, [], settings())
    assert res.picks[0].url == "https://a.com/1" and res.picks[0].score == 8


class FakeMessages:
    """Имитация client.beta.messages: веб-поиск с одной паузой, затем ранжирование."""

    def __init__(self):
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        if "tools" in kw:
            if len([c for c in self.calls if "tools" in c]) == 1:
                return SimpleNamespace(
                    stop_reason="pause_turn",
                    content=[SimpleNamespace(type="server_tool_use", text=None)],
                )
            return SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(type="text", text="1. Found https://c.com/3 about coffee")],
            )
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(CURATION))])


def test_anthropic_curator_resumes_pause_turn_and_ranks():
    fake = FakeMessages()
    client = SimpleNamespace(beta=SimpleNamespace(messages=fake))
    cur = AnthropicCurator("claude-opus-5", web_search=True, client=client)
    res = cur.curate(CANDS, ["done"], settings())

    assert res.picks[0].title == "Coffee and memory"
    assert len(fake.calls) == 3
    first, resumed, rank = fake.calls
    assert first["tools"][0]["type"] == "web_search_20260209"
    assert first["fallbacks"] == "default" and first["thinking"] == {"type": "adaptive"}
    assert resumed["messages"][-1]["role"] == "assistant"  # продолжение без лишнего сообщения
    assert rank["output_config"]["format"]["type"] == "json_schema"
    assert "https://c.com/3" in rank["messages"][0]["content"]
