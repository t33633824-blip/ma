from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class SourceDoc(BaseModel):
    """Исходный материал: статья, транскрипт, пресс-релиз."""

    url: str
    title: str = ""
    text: str


class Script(BaseModel):
    """Сценарий ролика. Это же JSON-схема для структурированного ответа нейросети."""

    title: str = Field(description="Заголовок ролика до 60 символов, без кликбейта")
    hook: str = Field(description="Первая фраза, 1-2 предложения, цепляет за первые 3 секунды")
    body: str = Field(description="Основной пересказ своими словами, 4-8 коротких предложений")
    cta: str = Field(description="Финальная фраза с вопросом к зрителю для комментариев")
    description: str = Field(description="Описание для платформы, 2-3 предложения, с упоминанием источника")
    tags: list[str] = Field(description="5-10 тегов без решётки")

    @property
    def narration(self) -> str:
        return " ".join(part.strip() for part in (self.hook, self.body, self.cta) if part.strip())


@dataclass
class WordTiming:
    word: str
    start: float
    end: float


@dataclass
class TTSResult:
    wav_path: str
    words: list[WordTiming] = field(default_factory=list)
    """Тайминги слов, если движок отдаёт их сам. Пустой список = нужно выравнивание через whisper."""
