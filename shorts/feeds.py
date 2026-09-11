from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import httpx
from pydantic import BaseModel

log = logging.getLogger(__name__)


class Candidate(BaseModel):
    url: str
    title: str
    summary: str = ""
    source: str = ""
    published: str = ""  # ISO-8601 или пусто
    kind: str = "article"  # article | story


class FeedSpec(BaseModel):
    url: str
    kind: str = "article"


def read_feed_list(path: Path) -> list[FeedSpec]:
    """Строка вида `URL` или `story URL` (истории с Reddit). Строки с # игнорируются."""
    if not path.exists():
        return []
    specs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0] in ("story", "article"):
            specs.append(FeedSpec(url=parts[1].strip(), kind=parts[0]))
        else:
            specs.append(FeedSpec(url=line))
    return specs


def fetch_feed(url: str, timeout: float = 20.0, kind: str = "article") -> list[Candidate]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; shorts-pipeline/0.1)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
    }
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        raw = client.get(url).raise_for_status().content
    return parse_feed(raw, source=url, kind=kind)


def parse_feed(raw: bytes | str, source: str = "", kind: str = "article") -> list[Candidate]:
    parsed = feedparser.parse(raw)
    feed_title = parsed.feed.get("title", "") or source
    out: list[Candidate] = []
    for e in parsed.entries:
        link = e.get("link") or ""
        if not link:
            continue
        published = ""
        st = e.get("published_parsed") or e.get("updated_parsed")
        if st:
            published = datetime.fromtimestamp(time.mktime(st), tz=timezone.utc).isoformat()
        html = e.get("summary", "") or ""
        if kind == "story":  # у Reddit полный текст поста лежит в content
            html = (e.get("content", [{}])[0].get("value", "") or html)
        summary = _strip_html(html)[: 700 if kind == "story" else 400]
        out.append(Candidate(url=link, title=(e.get("title") or "").strip(), summary=summary, source=feed_title, published=published, kind=kind))
    return out


def collect_candidates(feeds: list[FeedSpec], max_age_days: int) -> list[Candidate]:
    """Собирает записи из всех лент, отбрасывает старые и дубли по URL."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    seen: set[str] = set()
    out: list[Candidate] = []
    for spec in feeds:
        url = spec.url
        try:
            items = fetch_feed(url, kind=spec.kind)
        except Exception as e:  # noqa: BLE001
            log.warning("Лента недоступна %s: %s", url, e)
            continue
        for c in items:
            if c.published and datetime.fromisoformat(c.published) < cutoff:
                continue
            key = c.url.split("#")[0].rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
        log.info("Лента %s: %d записей", url, len(items))
    return out


def _strip_html(text: str) -> str:
    import re

    import html

    text = html.unescape(re.sub(r"<[^>]+>", " ", text)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()
