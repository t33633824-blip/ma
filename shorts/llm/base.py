from __future__ import annotations

from typing import Protocol

from ..config import Settings
from ..models import Script, SourceDoc

SYSTEM_PROMPT = """Ты сценарист коротких вертикальных роликов для русскоязычной аудитории.
Тебе дают западный материал (статью, исследование, транскрипт). Ты НЕ переводишь его,
а пересказываешь своими словами: оставляешь только самое интересное, объясняешь просто,
добавляешь контекст, который нужен русскоязычному зрителю.

Правила:
- Тема канала: {topic}. Стиль: {style}.
- Длина озвучки примерно {seconds} секунд, это около {words} слов на всё вместе.
- Крючок в первой фразе: конкретный факт, парадокс или вопрос, никаких "сегодня мы поговорим".
- Короткие предложения. Никаких вводных слов, канцелярита и англицизмов без нужды.
- Не выдумывай факты, которых нет в материале. Если чего-то нет, не пиши.
- Числа пиши словами или так, чтобы озвучка прочитала правильно (например "двадцать пять процентов").
- Заголовок честный, без кликбейта: платформы за него наказывают.
- В описании упомяни, что ролик сделан по мотивам источника, и дай его название."""

USER_PROMPT = """Источник: {url}
Заголовок источника: {title}

Текст источника:
\"\"\"
{text}
\"\"\"

Составь сценарий ролика по правилам выше."""


def build_prompts(doc: SourceDoc, settings: Settings) -> tuple[str, str]:
    words = int(settings.target_seconds * 2.3)  # ~2.3 слова в секунду для русской речи
    system = SYSTEM_PROMPT.format(
        topic=settings.channel_topic,
        style=settings.channel_style,
        seconds=settings.target_seconds,
        words=words,
    )
    user = USER_PROMPT.format(url=doc.url, title=doc.title or "(нет)", text=doc.text)
    return system, user


def script_json_schema() -> dict:
    schema = Script.model_json_schema()
    schema["additionalProperties"] = False
    return schema


class LLM(Protocol):
    def generate_script(self, doc: SourceDoc, settings: Settings) -> Script: ...
