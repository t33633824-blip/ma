from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from .config import load_settings


def cmd_make(args: argparse.Namespace) -> int:
    from .pipeline import make_short

    settings = load_settings()
    out = make_short(
        args.target,
        settings,
        script_path=args.script,
        background=args.background,
        out_dir=Path(args.out) if args.out else None,
    )
    print(out / "video.mp4")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    from .curator import discover

    settings = load_settings()
    if args.count:
        settings.curator_picks = args.count
    if args.no_web:
        settings.curator_web_search = False
    added = discover(settings)
    print(f"Добавлено тем в очередь: {len(added)} (файл {settings.queue_file})")
    return 0


def cmd_queue(_: argparse.Namespace) -> int:
    from .queue import Queue

    settings = load_settings()
    q = Queue(settings.queue_file)
    if not q.items:
        print("Очередь пуста. Запусти: python -m shorts discover")
        return 0
    for item in sorted(q.items, key=lambda x: (x.status != "pending", -x.score)):
        mark = {"pending": "·", "done": "✓", "failed": "✗", "skipped": "-"}[item.status]
        print(f"{mark} [{item.score:2d}] {item.title}\n      {item.url}")
        if item.video_dir:
            print(f"      → {item.video_dir}")
        if item.error:
            print(f"      ошибка: {item.error[:200]}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Берёт лучшие темы из очереди и делает ролики. Ошибки не останавливают остальные."""
    from .pipeline import make_short
    from .queue import Queue

    settings = load_settings()
    q = Queue(settings.queue_file)
    items = q.pending(args.count)
    if not items:
        print("В очереди нет тем. Запусти: python -m shorts discover")
        return 0
    failures = 0
    for item in items:
        print(f"▶ {item.title}")
        try:
            out = make_short(item.url, settings)
            q.mark(item, "done", video_dir=str(out))
            print(f"  готово: {out / 'video.mp4'}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            q.mark(item, "failed", error=str(e))
            logging.getLogger(__name__).exception("Не удалось сделать ролик: %s", item.url)
            print(f"  ошибка: {e}")
        q.save()
    return 1 if failures == len(items) else 0


def cmd_backgrounds(args: argparse.Namespace) -> int:
    from .backgrounds import fetch_pexels, generate_background

    settings = load_settings()
    settings.gameplay_dir.mkdir(parents=True, exist_ok=True)
    if args.action == "generate":
        for i in range(args.count):
            seed = (args.seed + i) if args.seed is not None else None
            dest = settings.gameplay_dir / f"generated-{args.scene}-{int(__import__('time').time())}-{i}.mp4"
            generate_background(str(dest), scene=args.scene, seconds=args.minutes * 60, width=settings.video_width, height=settings.video_height, seed=seed, balls=args.balls)
            print(dest)
        return 0
    saved = fetch_pexels(args.query, args.count, settings.pexels_api_key, settings.gameplay_dir)
    for p in saved:
        print(p)
    print(f"Скачано: {len(saved)}")
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    """Проверяет, что всё нужное на месте, и подсказывает, чего не хватает."""
    from .background import list_gameplay
    from .ffmpeg import ffmpeg_exe

    s = load_settings()
    ok = True

    def report(good: bool, msg: str, hint: str = "") -> None:
        nonlocal ok
        ok = ok and good
        print(("  ✓ " if good else "  ✗ ") + msg + (f"\n      → {hint}" if hint and not good else ""))

    print("ffmpeg")
    try:
        report(True, ffmpeg_exe())
    except Exception as e:  # noqa: BLE001
        report(False, f"не найден ({e})", "apt install ffmpeg или pip install imageio-ffmpeg")

    print(f"Куратор: {s.curator_provider}")
    if s.curator_provider == "anthropic":
        report(bool(s.anthropic_api_key), "ANTHROPIC_API_KEY задан", "добавь ключ в .env или CURATOR_PROVIDER=ollama")
    report(s.feeds_file.exists(), f"список лент {s.feeds_file}", "создай feeds.txt, по одной ссылке RSS в строке")

    print(f"Автор: {s.writer_provider}")
    if s.writer_provider == "ollama":
        from .llm.ollama_llm import OllamaLLM

        alive = OllamaLLM(s.ollama_url, s.ollama_model).is_available()
        report(alive, f"Ollama на {s.ollama_url}", "установи https://ollama.com и запусти: ollama serve")
        if alive:
            print(f"      модель: {s.ollama_model} (ollama pull {s.ollama_model}, если ещё не скачана)")
    else:
        report(bool(s.anthropic_api_key), "ANTHROPIC_API_KEY задан", "добавь ключ в .env")

    print(f"TTS: {s.tts_provider}")
    if s.tts_provider == "piper":
        voice = s.piper_dir / f"{s.piper_voice}.onnx"
        report(voice.exists(), f"голос {voice}", f"python -m piper.download_voices --download-dir {s.piper_dir} {s.piper_voice}")
    elif s.tts_provider == "elevenlabs":
        report(bool(s.elevenlabs_api_key and s.elevenlabs_voice_id), "ключ и voice_id ElevenLabs", "заполни .env")
    else:
        report(True, f"edge-tts голос {s.edge_voice}")

    print("Фон")
    clips = list_gameplay(s.gameplay_dir)
    report(bool(clips), f"{len(clips)} видео в {s.gameplay_dir}", "положи mp4 с геймплеем, иначе будет тестовая заглушка")

    print("Шрифт")
    fc = shutil.which("fc-list")
    if fc:
        import subprocess

        fonts = subprocess.run([fc, ":family"], capture_output=True, text=True).stdout
        report(s.subtitle_font in fonts, f"{s.subtitle_font}", "установи шрифт или поменяй SUBTITLE_FONT")
    else:
        print("  ? fc-list недоступен, шрифт не проверен")

    print("\nВсё готово" if ok else "\nЕсть проблемы, см. подсказки выше")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shorts", description="Конвейер вертикальных роликов")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_make = sub.add_parser("make", help="сделать ролик из статьи (URL) или текстового файла")
    p_make.add_argument("target", help="URL статьи или путь к .txt")
    p_make.add_argument("--script", help="готовый script.json, пропустить нейросеть")
    p_make.add_argument("--background", help="конкретный файл фона вместо случайного")
    p_make.add_argument("--out", help="папка результата (по умолчанию OUT_DIR)")
    p_make.set_defaults(func=cmd_make)

    p_disc = sub.add_parser("discover", help="найти и отобрать темы в очередь (куратор)")
    p_disc.add_argument("--count", type=int, help="сколько тем отобрать (CURATOR_PICKS)")
    p_disc.add_argument("--no-web", action="store_true", help="без веб-поиска, только RSS")
    p_disc.set_defaults(func=cmd_discover)

    p_run = sub.add_parser("run", help="сделать ролики по лучшим темам из очереди")
    p_run.add_argument("--count", type=int, default=1, help="сколько роликов сделать за запуск")
    p_run.set_defaults(func=cmd_run)

    p_q = sub.add_parser("queue", help="показать очередь тем")
    p_q.set_defaults(func=cmd_queue)

    p_bg = sub.add_parser("backgrounds", help="сделать или скачать фоновые видео")
    bg_sub = p_bg.add_subparsers(dest="action", required=True)
    p_gen = bg_sub.add_parser("generate", help="нарисовать залипательную анимацию")
    p_gen.add_argument("--scene", default="random", choices=["random", "bounce", "split", "flow"], help="bounce: шарики в кольце; split: шарик делится при ударе; flow: поток частиц")
    p_gen.add_argument("--minutes", type=float, default=3.0, help="длина одного файла в минутах")
    p_gen.add_argument("--count", type=int, default=1, help="сколько файлов сделать")
    p_gen.add_argument("--balls", type=int, default=3)
    p_gen.add_argument("--seed", type=int, help="зерно случайности, для повторяемости")
    p_fetch = bg_sub.add_parser("fetch", help="скачать бесплатные вертикальные ролики с Pexels")
    p_fetch.add_argument("--query", default="satisfying", help="поисковый запрос, например: satisfying, slime, kinetic sand, hydraulic press, ocean waves")
    p_fetch.add_argument("--count", type=int, default=10)
    p_bg.set_defaults(func=cmd_backgrounds)

    p_doc = sub.add_parser("doctor", help="проверить окружение")
    p_doc.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
