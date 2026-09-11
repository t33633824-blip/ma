from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict
from pathlib import Path

from .align import align_script_to_timings, split_words, transcribe_words
from .background import pick_background
from .config import Settings
from .ffmpeg import media_duration
from .llm import get_writer
from .models import Script, SourceDoc, WordTiming
from .render import render_video
from .sources import fetch_article, load_text_file
from .subtitles import SubtitleStyle, build_ass
from .tts import get_tts

log = logging.getLogger(__name__)


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^\w]+", "-", text.lower(), flags=re.UNICODE).strip("-")
    return slug[:max_len].rstrip("-") or "video"


def load_source(target: str) -> SourceDoc:
    if target.startswith(("http://", "https://")):
        return fetch_article(target)
    return load_text_file(target)


def make_short(
    target: str,
    settings: Settings,
    script_path: str | None = None,
    background: str | None = None,
    out_dir: Path | None = None,
) -> Path:
    """Полный цикл: источник -> сценарий -> озвучка -> тайминги -> субтитры -> видео.

    Возвращает папку с результатом. Каждый промежуточный файл сохраняется, чтобы
    любой шаг можно было переделать руками.
    """
    t0 = time.time()
    if script_path:
        script = Script.model_validate_json(Path(script_path).read_text(encoding="utf-8"))
        doc = SourceDoc(url=target, title=script.title, text="")
        log.info("Сценарий взят из файла %s", script_path)
    else:
        doc = load_source(target)
        log.info("Источник: %s (%d символов)", doc.title or doc.url, len(doc.text))
        writer = get_writer(settings)
        script = writer.generate_script(doc, settings)
        log.info("Сценарий готов: %s", script.title)

    work = (out_dir or settings.out_dir) / f"{time.strftime('%Y%m%d-%H%M%S')}-{slugify(script.title)}"
    work.mkdir(parents=True, exist_ok=True)
    (work / "source.txt").write_text(f"{doc.url}\n{doc.title}\n\n{doc.text}", encoding="utf-8")
    (work / "script.json").write_text(script.model_dump_json(indent=2), encoding="utf-8")

    narration = script.narration
    (work / "narration.txt").write_text(narration, encoding="utf-8")
    wav = str(work / "voice.wav")
    tts = get_tts(settings)
    tts_result = tts.synthesize(narration, wav)
    duration = media_duration(wav)
    log.info("Озвучка: %.1f c (%s)", duration, settings.tts_provider)

    script_words = split_words(narration)
    if tts_result.words:
        heard = tts_result.words
    else:
        log.info("Тайминги слов через faster-whisper (%s)…", settings.whisper_model)
        heard = transcribe_words(wav, settings.whisper_model, str(settings.whisper_dir))
    words = align_script_to_timings(script_words, heard, duration)
    (work / "words.json").write_text(json.dumps([asdict(w) for w in words], ensure_ascii=False, indent=1), encoding="utf-8")

    style = SubtitleStyle(font=settings.subtitle_font, width=settings.video_width, height=settings.video_height)
    ass = build_ass(words, style, per_line=settings.subtitle_words_per_line)
    subs = work / "subs.ass"
    subs.write_text(ass, encoding="utf-8")

    bg = pick_background(settings.gameplay_dir, duration, forced=background)
    out_mp4 = str(work / "video.mp4")
    render_video(bg, wav, str(subs), out_mp4, settings.video_width, settings.video_height)

    meta = {
        "title": script.title,
        "description": script.description,
        "tags": script.tags,
        "source_url": doc.url,
        "duration_seconds": round(duration, 2),
        "background": asdict(bg),
        "writer": settings.writer_provider,
        "tts": settings.tts_provider,
        "altered_content": True,  # для отметки «изменённый или синтетический контент» при загрузке
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    (work / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Готово за %.0f c: %s", meta["elapsed_seconds"], out_mp4)
    return work


def words_from_json(path: str) -> list[WordTiming]:
    return [WordTiming(**w) for w in json.loads(Path(path).read_text(encoding="utf-8"))]
