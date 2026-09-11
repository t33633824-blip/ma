from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Pick(BaseModel):
    """Одна отобранная куратором тема."""

    url: str = Field(description="Ссылка на первоисточник")
    title: str = Field(description="Оригинальный заголовок")
    reason: str = Field(description="Почему это зайдёт русскоязычной аудитории, 1-2 предложения")
    hook_idea: str = Field(description="Идея крючка для первых трёх секунд, на русском")
    score: int = Field(description="Оценка потенциала: целое число от 1 до 10")

    @field_validator("score", mode="before")
    @classmethod
    def _clamp(cls, v):
        return max(1, min(10, int(v)))


class Curation(BaseModel):
    picks: list[Pick] = Field(description="Отобранные темы, лучшие первыми")
    rejected_note: str = Field(description="Коротко: что отброшено и почему")


class QueueItem(Pick):
    status: Literal["pending", "done", "failed", "skipped"] = "pending"
    added_at: str = ""
    finished_at: str = ""
    video_dir: str = ""
    error: str = ""


def _norm(url: str) -> str:
    return url.split("#")[0].split("?utm")[0].rstrip("/").lower()


class Queue:
    """Очередь тем в одном JSON-файле. Служит и историей: сделанные темы не предлагаются повторно."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.items: list[QueueItem] = []
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.items = [QueueItem.model_validate(x) for x in data]

    def save(self) -> None:
        self.path.write_text(
            json.dumps([x.model_dump() for x in self.items], ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def known_urls(self) -> set[str]:
        return {_norm(x.url) for x in self.items}

    def add(self, picks: list[Pick]) -> list[QueueItem]:
        known = self.known_urls()
        added: list[QueueItem] = []
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for p in picks:
            if _norm(p.url) in known:
                continue
            item = QueueItem(**p.model_dump(), added_at=now)
            self.items.append(item)
            known.add(_norm(p.url))
            added.append(item)
        return added

    def pending(self, limit: int | None = None) -> list[QueueItem]:
        items = sorted((x for x in self.items if x.status == "pending"), key=lambda x: -x.score)
        return items[:limit] if limit else items

    def recent_titles(self, limit: int = 40) -> list[str]:
        return [x.title for x in self.items[-limit:]]

    def mark(self, item: QueueItem, status: Literal["done", "failed", "skipped"], video_dir: str = "", error: str = "") -> None:
        item.status = status
        item.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        item.video_dir = video_dir
        item.error = error
