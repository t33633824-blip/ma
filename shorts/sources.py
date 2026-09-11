from __future__ import annotations

import httpx
import trafilatura

from .models import SourceDoc

MAX_CHARS = 20_000
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) shorts-pipeline/0.1"}


def is_reddit(url: str) -> bool:
    return "reddit.com/" in url


def fetch_reddit_post(url: str, max_comments: int = 5, timeout: float = 30.0) -> SourceDoc:
    """Пост Reddit и несколько верхних комментариев через RSS самого поста (не требует ключа API)."""
    import html as html_mod
    import re

    import feedparser

    rss_url = url.split("?")[0].rstrip("/") + ".rss"
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=UA) as client:
        raw = client.get(rss_url).raise_for_status().content
    feed = feedparser.parse(raw)
    if not feed.entries:
        raise ValueError(f"Reddit не отдал пост: {url}")

    def body(entry) -> str:
        html = entry.get("content", [{}])[0].get("value", "") or entry.get("summary", "")
        text = html_mod.unescape(re.sub(r"<[^>]+>", " ", html))
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"submitted by\s+/u/\S+.*$", "", text).strip()
        return text

    post = feed.entries[0]
    title = (post.get("title") or "").strip()
    parts = [body(post)]
    comments = []
    for e in feed.entries[1:]:
        t = body(e)
        if len(t) > 40 and "[removed]" not in t and "[deleted]" not in t:
            comments.append(t)
        if len(comments) >= max_comments:
            break
    if comments:
        parts.append("\n\nЛучшие комментарии:\n" + "\n".join(f"- {c[:600]}" for c in comments))
    text = "\n".join(parts)
    if len(text) < 200:
        raise ValueError(f"Слишком короткий пост: {url}")
    return SourceDoc(url=url, title=title, text=text[:MAX_CHARS], kind="story")


def fetch_article(url: str, timeout: float = 30.0) -> SourceDoc:
    """Скачивает страницу и вытаскивает основной текст без меню и рекламы."""
    if is_reddit(url):
        return fetch_reddit_post(url, timeout=timeout)
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=UA) as client:
        html = client.get(url).raise_for_status().text
    return extract_from_html(html, url)


def extract_from_html(html: str, url: str) -> SourceDoc:
    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=False) or ""
    meta = trafilatura.extract_metadata(html, default_url=url)
    title = (meta.title if meta and meta.title else "") or ""
    if not text.strip():
        raise ValueError(f"Не удалось извлечь текст со страницы: {url}")
    return SourceDoc(url=url, title=title, text=text[:MAX_CHARS])


def load_text_file(path: str) -> SourceDoc:
    """Для случаев, когда материал уже лежит в файле (транскрипт, заметка)."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return SourceDoc(url=f"file://{path}", title="", text=text[:MAX_CHARS])
