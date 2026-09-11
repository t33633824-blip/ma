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

    print(f"LLM: {s.llm_provider}")
    if s.llm_provider == "ollama":
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
