from __future__ import annotations

import logging
from typing import Protocol

from ..config import Settings
from ..models import Script, SourceDoc

log = logging.getLogger(__name__)

WORDS_PER_SECOND = 2.3  # средний темп русской озвучки

SYSTEM_PROMPT = """Ты сценарист коротких вертикальных роликов для русскоязычной аудитории.
Тебе дают западный материал (статью, исследование, транскрипт). Ты НЕ переводишь его,
а пересказываешь своими словами: оставляешь только самое интересное, объясняешь просто,
добавляешь контекст, который нужен русскоязычному зрителю.

Правила:
- Тема канала: {topic}. Стиль: {style}.
- Длина озвучки примерно {seconds} секунд, это не больше {words} слов на всё вместе.
- Крючок в первой фразе: конкретный факт, парадокс или вопрос, никаких "сегодня мы поговорим".
- Обращайся к зрителю на "ты", как к другу. Одна мысль на предложение.
- Драматургия: сначала интрига, потом что нашли, потом почему это важно именно тебе, в конце вопрос.
- Короткие предложения. Никаких вводных слов, канцелярита и англицизмов без нужды.
- Пиши грамотно: следи за родом, падежом и числом ("ИИ решил", а не "ИИ решило"). Только кириллица внутри русских слов.
- Не выдумывай факты, которых нет в материале. Если чего-то нет, не пиши.
- Числа пиши словами или так, чтобы озвучка прочитала правильно (например "двадцать пять процентов").
- Аббревиатуры и сокращения не используй: "искусственный интеллект", а не "ИИ"; "учёные из НАСА" можно, "US" и "AI" нельзя. Названия компаний и изданий пиши по-русски: гугл, нейчер.
- Текст пойдёт в озвучку: не используй многоточия, тире, скобки и кавычки, они превращаются в паузы. Запятая и точка достаточно.
- Заголовок честный, без кликбейта: платформы за него наказывают.
- В описании упомяни, что ролик сделан по мотивам источника, и дай его название."""

STORY_SYSTEM_PROMPT = """Ты рассказчик коротких вертикальных роликов с историями из интернета для русскоязычной аудитории.
Тебе дают пост с Reddit и несколько комментариев. Ты пересказываешь историю по-русски так,
будто рассказываешь другу за столом: живо, с деталями, с нарастанием и развязкой.

Правила:
- Стиль: {style}. Длина озвучки примерно {seconds} секунд, это не больше {words} слов на всё вместе.
- Первая фраза сразу бросает в ситуацию: "Парень решил разыграть друзей на вечеринке, и через минуту его чуть не побили".
- Рассказывай от третьего лица ("один парень", "одна девушка") или как пересказ ("автор пишет, что"). Имена не называй, ники не упоминай.
- Сохрани поворот и развязку, убери лишние подробности. Если комментарии добавляют изюминку, можно упомянуть одной фразой.
- Адаптируй реалии: доллары можно оставить, но непонятные русскому зрителю названия объясни или замени описанием.
- Без мата, без насилия и без откровенных подробностей, платформы такое режут.
- Одна мысль на предложение, разговорные обороты, но грамотно. Только кириллица внутри русских слов.
- Без аббревиатур и латиницы: не "AITA", а "автор спрашивает, не перегнул ли он"; названия пиши по-русски.
- Текст пойдёт в озвучку: никаких многоточий, тире, скобок и кавычек. Запятая и точка достаточно.
- В конце вопрос к зрителю: как бы он поступил или было ли у него такое.
- Заголовок до 60 символов, без кликбейта. В описании упомяни, что история взята с Reddit."""

STORY_USER_PROMPT = """Пост: {title}
Ссылка: {url}

\"\"\"
{text}
\"\"\"

Перескажи эту историю по правилам выше."""

USER_PROMPT = """Источник: {url}
Заголовок источника: {title}

Текст источника:
\"\"\"
{text}
\"\"\"

Составь сценарий ролика по правилам выше."""

POLISH_SYSTEM = """Ты редактор русскоязычного канала коротких роликов. Тебе дают черновик сценария в JSON.
Верни тот же JSON с теми же полями, но выправленный:
- исправь ошибки русского языка: согласование рода, падежа и числа, порядок слов, опечатки;
- убери канцелярит, штампы и лишние вводные слова, замени ненужные англицизмы;
- сделай фразы короче и разговорнее, как рассказ другу, но без фамильярности;
- сохрани все факты и структуру, ничего не добавляй от себя;
- убери многоточия, тире, скобки и кавычки: текст идёт в озвучку, они дают паузы;
- аббревиатуры раскрой словами (искусственный интеллект вместо ИИ), латиницу замени русским написанием;
- внутри русских слов только кириллица, латинские буквы в русских словах это ошибка;
- общая длина hook + body + cta не больше {words} слов (сейчас {current} слов){shorten};
- заголовок до 60 символов, теги без решётки."""

POLISH_USER = """Черновик:
{script_json}"""


def build_prompts(doc: SourceDoc, settings: Settings) -> tuple[str, str]:
    words = target_words(settings)
    if doc.kind == "story":
        system = STORY_SYSTEM_PROMPT.format(style=settings.channel_style, seconds=settings.target_seconds, words=words)
        user = STORY_USER_PROMPT.format(url=doc.url, title=doc.title or "(нет)", text=doc.text)
        return system, user
    system = SYSTEM_PROMPT.format(
        topic=settings.channel_topic, style=settings.channel_style, seconds=settings.target_seconds, words=words
    )
    user = USER_PROMPT.format(url=doc.url, title=doc.title or "(нет)", text=doc.text)
    return system, user


def target_words(settings: Settings) -> int:
    return int(settings.target_seconds * WORDS_PER_SECOND)


def count_words(script: Script) -> int:
    return len(script.narration.split())


_UNSUPPORTED_KEYS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength", "minItems", "maxItems", "pattern", "format")


def strict_schema(schema: dict) -> dict:
    """Приводит JSON-схему к виду, который принимает структурированный вывод Anthropic:
    additionalProperties: false на каждом объекте, без числовых и строковых ограничений
    (они остаются в описаниях полей и проверяются pydantic после ответа). Ollama такая схема тоже устраивает."""
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
        for key in _UNSUPPORTED_KEYS:
            schema.pop(key, None)
        for v in schema.values():
            strict_schema(v)
    elif isinstance(schema, list):
        for v in schema:
            strict_schema(v)
    return schema


def script_json_schema() -> dict:
    return strict_schema(Script.model_json_schema())


class LLM(Protocol):
    def complete_json(self, system: str, user: str, schema: dict, temperature: float = 0.7) -> dict:
        """Один запрос к модели со структурированным ответом по схеме."""
        ...

    def generate_script(self, doc: SourceDoc, settings: Settings) -> Script: ...


def generate_script(llm: LLM, doc: SourceDoc, settings: Settings) -> Script:
    system, user = build_prompts(doc, settings)
    return Script.model_validate(llm.complete_json(system, user, script_json_schema(), temperature=0.7))


def polish_script(llm: LLM, script: Script, settings: Settings, shorten: bool = False) -> Script:
    """Редакторский проход: грамматика, живость, хронометраж. Та же модель, вторая попытка всегда чище первой."""
    words = target_words(settings)
    current = count_words(script)
    note = ", обязательно сократи: убери второстепенные детали, а не факты" if shorten else ""
    system = POLISH_SYSTEM.format(words=words, current=current, shorten=note)
    user = POLISH_USER.format(script_json=script.model_dump_json(indent=1))
    return Script.model_validate(llm.complete_json(system, user, script_json_schema(), temperature=0.3))


def write_script(llm: LLM, doc: SourceDoc, settings: Settings) -> Script:
    """Черновик -> редактура -> при необходимости сокращение, пока не уложимся в хронометраж."""
    script = generate_script(llm, doc, settings)
    log.info("Черновик: %d слов при цели %d", count_words(script), target_words(settings))
    if not settings.writer_polish:
        return script
    limit = int(target_words(settings) * 1.15)
    script = polish_script(llm, script, settings, shorten=count_words(script) > limit)
    for _ in range(2):
        if count_words(script) <= limit:
            break
        log.info("Всё ещё длинно: %d слов, сокращаю", count_words(script))
        script = polish_script(llm, script, settings, shorten=True)
    log.info("После редактуры: %d слов", count_words(script))
    return script
