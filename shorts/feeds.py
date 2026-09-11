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


def read_feed_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def fetch_feed(url: str, timeout: float = 20.0) -> list[Candidate]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; shorts-pipeline/0.1)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
    }
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        raw = client.get(url).raise_for_status().content
    return parse_feed(raw, source=url)


def parse_feed(raw: bytes | str, source: str = "") -> list[Candidate]:
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
        summary = _strip_html(e.get("summary", "") or "")[:400]
        out.append(Candidate(url=link, title=(e.get("title") or "").strip(), summary=summary, source=feed_title, published=published))
    return out


def collect_candidates(feed_urls: list[str], max_age_days: int) -> list[Candidate]:
    """Собирает записи из всех лент, отбрасывает старые и дубли по URL."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    seen: set[str] = set()
    out: list[Candidate] = []
    for url in feed_urls:
        try:
            items = fetch_feed(url)
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

    text = re.sub(r"<[^>]+>", " ", text).replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()
