"""Раскадровка: режем озвучку на сцены по 5-7 секунд и просим модель описать картинку для каждой."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import BaseModel, Field

from .config import Settings
from .llm.base import LLM, strict_schema
from .models import Script, WordTiming

log = logging.getLogger(__name__)


@dataclass
class Segment:
    text: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def segment_words(words: list[WordTiming], target: float = 5.5, min_len: float = 3.0, max_len: float = 7.5, total: float | None = None) -> list[Segment]:
    """Группирует слова в сцены: стараемся резать на границе предложения после min_len,
    обязательно режем при max_len. Последняя сцена дотягивается до конца озвучки."""
    if not words:
        return []
    segments: list[Segment] = []
    buf: list[WordTiming] = []
    seg_start = words[0].start
    for i, w in enumerate(words):
        buf.append(w)
        length = w.end - seg_start
        ends_sentence = w.word.rstrip().endswith((".", "!", "?"))
        ends_clause = w.word.rstrip().endswith((",", ";", ":"))
        next_start = words[i + 1].start if i + 1 < len(words) else None
        cut = False
        if next_start is None:
            cut = True
        elif length >= max_len:
            cut = True
        elif length >= min_len and ends_sentence:
            cut = True
        elif length >= target and ends_clause:
            cut = True
        if cut:
            end = next_start if next_start is not None else w.end
            segments.append(Segment(" ".join(x.word for x in buf), seg_start, end))
            buf = []
            seg_start = end
    if total is not None and segments and segments[-1].end < total:
        segments[-1].end = total
    if segments:
        segments[0].start = 0.0
    return segments


SCENE_SYSTEM = """You are a director creating AI-generated b-roll for a vertical (9:16) short video in Russian.
For each narration segment write ONE prompt in English for a text-to-video model.

Rules for every prompt:
- Describe a concrete visual scene that illustrates the segment: subject, setting, action, camera movement, lighting. 2-3 sentences.
- Keep one consistent visual style across all scenes: {style}.
- Vertical framing, the subject in the centre of the frame.
- Slow, smooth camera movement (slow push-in, slow pan, gentle handheld). Never static.
- No text, no captions, no logos, no user interfaces, no famous people, no close-up human faces (medium and wide shots are fine), no gore.
- Prefer objects, landscapes, hands, laboratories, cities, nature, abstract macro shots, and symbolic images over literal people talking.
- Return exactly {n} prompts in the same order as the segments."""

SCENE_USER = """Video title: {title}

Narration segments (Russian):
{segments}

Return the prompts."""


class ScenePrompt(BaseModel):
    prompt: str = Field(description="English text-to-video prompt, 2-3 sentences")


class Storyboard(BaseModel):
    scenes: list[ScenePrompt] = Field(description="Exactly one prompt per narration segment, same order")


def plan_scenes(llm: LLM, script: Script, segments: list[Segment], settings: Settings) -> list[str]:
    system = SCENE_SYSTEM.format(style=settings.video_style, n=len(segments))
    listed = "\n".join(f"{i + 1}. ({s.duration:.1f}s) {s.text}" for i, s in enumerate(segments))
    user = SCENE_USER.format(title=script.title, segments=listed)
    schema = strict_schema(Storyboard.model_json_schema())
    data = llm.complete_json(system, user, schema, temperature=0.6)
    prompts = [s.prompt.strip() for s in Storyboard.model_validate(data).scenes if s.prompt.strip()]
    if len(prompts) < len(segments):
        log.warning("Модель дала %d сцен вместо %d, недостающие повторим", len(prompts), len(segments))
        filler = prompts[-1] if prompts else f"Abstract slow-motion macro shot, {settings.video_style}"
        prompts += [filler] * (len(segments) - len(prompts))
    return prompts[: len(segments)]
