"""Куратор: ищет свежие материалы и отбирает темы для роликов.

По умолчанию это Claude с веб-поиском: он умеет искать в интернете и хорошо
оценивает, что зайдёт аудитории. Локальная модель через Ollama тоже может
ранжировать, но только то, что пришло из RSS-лент.
"""
from __future__ import annotations

import json
import logging
from typing import Protocol

from .config import Settings
from .feeds import Candidate
from .queue import Curation, Pick

log = logging.getLogger(__name__)

CURATOR_SYSTEM = """Ты редактор русскоязычного канала коротких вертикальных роликов.
Тема канала: {topic}. Стиль: {style}. Каждый ролик это пересказ одного западного материала
своими словами на 45-60 секунд с крючком в первые три секунды.

Твоя задача отобрать материалы, из которых получится сильный ролик. Критерии:
- есть один конкретный, неожиданный или спорный факт, который можно объяснить за минуту;
- материал свежий и его ещё не обсуждали все подряд;
- источник содержательный (исследование, разбор, репортаж), а не заметка в два абзаца и не пресс-релиз без сути;
- тема безопасна для монетизации: без трагедий, политики, медицинских советов и шок-контента;
- не повторяет темы, которые канал уже делал (список ниже).

Отбери не больше {n} лучших, оцени каждую от 1 до 10 и предложи идею крючка на русском.
Ссылки бери только те, что есть в списке кандидатов или в результатах поиска, ничего не выдумывай."""

RANK_USER = """Уже сделанные темы (не повторять):
{recent}

Кандидаты из RSS-лент:
{candidates}

{web_block}Выбери лучшие темы."""

WEB_SEARCH_USER = """Найди в интернете свежие (за последние {days} дней) англоязычные материалы по теме «{topic}»,
из которых получится интересный короткий ролик для русскоязычной аудитории.
Ищи исследования, разборы и репортажи с конкретными фактами, а не новости в два абзаца.
Верни список из 10-15 находок: заголовок, точная ссылка, 1-2 предложения о сути. Без вступлений и выводов."""


def format_candidates(cands: list[Candidate], limit: int = 80) -> str:
    lines = []
    for i, c in enumerate(cands[:limit], 1):
        date = c.published[:10] if c.published else "дата неизвестна"
        lines.append(f"{i}. [{c.source} | {date}] {c.title}\n   {c.url}\n   {c.summary}")
    return "\n".join(lines) if lines else "(пусто)"


def build_rank_prompts(cands: list[Candidate], recent_titles: list[str], web_findings: str, settings: Settings) -> tuple[str, str]:
    system = CURATOR_SYSTEM.format(
        topic=settings.channel_topic, style=settings.channel_style, n=settings.curator_picks
    )
    web_block = f"Находки из веб-поиска:\n{web_findings}\n\n" if web_findings.strip() else ""
    user = RANK_USER.format(
        recent="\n".join(f"- {t}" for t in recent_titles) or "- (пока ничего)",
        candidates=format_candidates(cands),
        web_block=web_block,
    )
    return system, user


def curation_schema() -> dict:
    from .llm.base import strict_schema

    return strict_schema(Curation.model_json_schema())


class Curator(Protocol):
    def curate(self, cands: list[Candidate], recent_titles: list[str], settings: Settings) -> Curation: ...


class AnthropicCurator:
    """Claude: сначала веб-поиск (если включён), потом ранжирование со структурированным ответом."""

    def __init__(self, model: str, api_key: str | None = None, web_search: bool = True, client=None):
        import anthropic

        self.model = model
        self.web_search = web_search
        self.client = client or (anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic())

    def _create(self, **kwargs):
        return self.client.beta.messages.create(
            model=self.model,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            thinking={"type": "adaptive"},
            **kwargs,
        )

    def search_web(self, settings: Settings, max_continuations: int = 5) -> str:
        user = WEB_SEARCH_USER.format(days=settings.curator_days, topic=settings.channel_topic)
        tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 8}]
        messages = [{"role": "user", "content": user}]
        response = self._create(max_tokens=16000, tools=tools, messages=messages)
        continuations = 0
        while response.stop_reason == "pause_turn" and continuations < max_continuations:
            # сервер сам продолжит с места остановки, доп. сообщение пользователя не нужно
            messages.append({"role": "assistant", "content": response.content})
            response = self._create(max_tokens=16000, tools=tools, messages=messages)
            continuations += 1
        if response.stop_reason == "refusal":
            log.warning("Веб-поиск: модель отказалась, продолжаем без него")
            return ""
        return "\n".join(block.text for block in response.content if block.type == "text")

    def curate(self, cands: list[Candidate], recent_titles: list[str], settings: Settings) -> Curation:
        web = ""
        if self.web_search:
            web = _cached_web_findings(settings)
            if web is None:
                log.info("Куратор: веб-поиск по теме «%s»…", settings.channel_topic)
                web = self.search_web(settings)
                _save_web_findings(settings, web)
        system, user = build_rank_prompts(cands, recent_titles, web, settings)
        response = self._create(
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": curation_schema()}},
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Куратор: модель отказалась ранжировать кандидатов")
        text = next(block.text for block in response.content if block.type == "text")
        return Curation.model_validate(json.loads(text))


WEB_CACHE_HOURS = 6


def _web_cache_path(settings: Settings):
    return settings.out_dir / "curator_web_cache.json"


def _cached_web_findings(settings: Settings) -> str | None:
    """Результат веб-поиска хранится несколько часов: если следующий шаг упал, поиск не повторяется."""
    import time

    path = _web_cache_path(settings)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if data.get("topic") != settings.channel_topic or time.time() - data.get("ts", 0) > WEB_CACHE_HOURS * 3600:
        return None
    log.info("Куратор: беру результаты веб-поиска из кэша (%s)", path)
    return data.get("text", "")


def _save_web_findings(settings: Settings, text: str) -> None:
    import time

    path = _web_cache_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ts": time.time(), "topic": settings.channel_topic, "text": text}, ensure_ascii=False), encoding="utf-8")


class OllamaCurator:
    """Локальный вариант: только ранжирование RSS-кандидатов, без поиска в интернете."""

    def __init__(self, base_url: str, model: str, timeout: float = 600.0, client=None):
        import httpx

        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = client or httpx.Client(timeout=timeout)

    def curate(self, cands: list[Candidate], recent_titles: list[str], settings: Settings) -> Curation:
        system, user = build_rank_prompts(cands, recent_titles, "", settings)
        payload = {
            "model": self.model,
            "stream": False,
            "format": curation_schema(),
            "options": {"temperature": 0.3},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        resp = self.client.post(f"{self.base_url}/api/chat", json=payload)
        resp.raise_for_status()
        return Curation.model_validate(json.loads(resp.json()["message"]["content"]))


def get_curator(settings: Settings) -> Curator:
    if settings.curator_provider == "anthropic":
        return AnthropicCurator(settings.curator_model, settings.anthropic_api_key or None, settings.curator_web_search)
    if settings.curator_provider == "ollama":
        return OllamaCurator(settings.ollama_url, settings.ollama_model)
    raise ValueError(f"Неизвестный CURATOR_PROVIDER: {settings.curator_provider}")


def filter_known(cands: list[Candidate], known_urls: set[str]) -> list[Candidate]:
    from .queue import _norm

    return [c for c in cands if _norm(c.url) not in known_urls]


def discover(settings: Settings) -> list[Pick]:
    """Полный цикл куратора: RSS + веб-поиск -> отбор -> очередь. Возвращает добавленные темы."""
    from .feeds import collect_candidates, read_feed_list
    from .queue import Queue

    queue = Queue(settings.queue_file)
    feeds = read_feed_list(settings.feeds_file)
    cands = collect_candidates(feeds, settings.curator_days) if feeds else []
    cands = filter_known(cands, queue.known_urls())
    log.info("Кандидатов из RSS после фильтра: %d", len(cands))

    curator = get_curator(settings)
    if not cands and not (settings.curator_provider == "anthropic" and settings.curator_web_search):
        log.warning("Нет кандидатов и веб-поиск выключен, отбирать нечего")
        return []
    curation = curator.curate(cands, queue.recent_titles(), settings)
    log.info("Куратор отбросил: %s", curation.rejected_note)
    added = queue.add(curation.picks)
    queue.save()
    for p in added:
        log.info("В очередь [%d/10] %s\n    %s\n    крючок: %s", p.score, p.title, p.url, p.hook_idea)
    return added
