from __future__ import annotations

import httpx
import trafilatura

from .models import SourceDoc

MAX_CHARS = 20_000


def fetch_article(url: str, timeout: float = 30.0) -> SourceDoc:
    """Скачивает страницу и вытаскивает основной текст без меню и рекламы."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; shorts-pipeline/0.1)"}
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
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
