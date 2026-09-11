# Shorts Pipeline

Автоматический конвейер вертикальных роликов: западная статья → пересказ на русском своими словами →
озвучка → субтитры по словам → готовый MP4 9:16 с геймплеем на фоне.

По умолчанию всё работает **локально**: Ollama для сценария, Piper для голоса, faster-whisper для таймингов.
Облачные варианты (Claude, edge-tts, ElevenLabs) включаются одной строкой в `.env`.

## Быстрый старт

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 1. Локальная нейросеть для сценариев
#    https://ollama.com  → ollama pull qwen2.5:7b
# 2. Русский голос Piper (один раз, ~60 МБ)
python -m piper.download_voices --download-dir models/piper ru_RU-irina-medium
# 3. Свои записи геймплея в assets/gameplay/*.mp4 (см. assets/gameplay/README.md)

cp .env.example .env      # при желании поправь тему канала и провайдеров
python -m shorts doctor   # проверит, что всё на месте
python -m shorts make https://example.com/some-article
```

Результат лежит в `out/<дата>-<заголовок>/`:

| Файл | Что это |
|---|---|
| `video.mp4` | готовый ролик 1080×1920, 30 fps |
| `script.json` | сценарий: заголовок, крючок, текст, вопрос, описание, теги |
| `narration.txt` | текст, который был озвучен |
| `voice.wav` | озвучка |
| `words.json` | тайминги каждого слова |
| `subs.ass` | субтитры, можно поправить и перерендерить |
| `meta.json` | заголовок, описание и теги для загрузки на платформу |

Модель whisper (`small`, ~460 МБ) скачается сама при первом запуске.

## Как это устроено

```
sources.py   ─ скачать статью, вычистить меню и рекламу (trafilatura)
llm/         ─ сценарий по строгой JSON-схеме: Ollama (локально) или Claude
tts/         ─ голос: Piper (локально), edge-tts (бесплатно, облако), ElevenLabs (платно)
align.py     ─ тайминги слов: faster-whisper слушает озвучку, слова сценария получают время
subtitles.py ─ ASS-субтитры по 3 слова, текущее слово подсвечено
background.py─ случайный фрагмент случайного геймплея из assets/gameplay
render.py    ─ ffmpeg: кроп до 9:16, наложение субтитров, микс с голосом
pipeline.py  ─ склейка шагов, все промежуточные файлы сохраняются
```

Если движок озвучки отдаёт тайминги сам (edge-tts, ElevenLabs), whisper не запускается.

## Полезные команды

```bash
python -m shorts make статья.txt                    # из текстового файла вместо URL
python -m shorts make URL --script out/.../script.json   # переозвучить готовый сценарий без нейросети
python -m shorts make URL --background assets/gameplay/minecraft.mp4
python -m shorts -v make URL                        # подробный лог, включая команду ffmpeg
pytest                                              # тесты
```

## Настройки (.env)

Все параметры описаны в `.env.example`. Главные:

- `LLM_PROVIDER=ollama|anthropic`, `OLLAMA_MODEL` (для русского хорошо `qwen2.5:7b`, `qwen2.5:14b`, `gemma3:12b`)
- `TTS_PROVIDER=piper|edge|elevenlabs`
- `CHANNEL_TOPIC`, `CHANNEL_STYLE`, `TARGET_SECONDS` задают тон и длину сценария
- `SUBTITLE_WORDS_PER_LINE`, `SUBTITLE_FONT`

## Правила, чтобы канал жил долго

- Ролик это пересказ своими словами, а не перевод и не копия. В описании указан источник.
- Фон только из собственного или разрешённого издателем геймплея, без музыки из игры. Фильмы не использовать.
- При загрузке отмечать «изменённый или синтетический контент» (в `meta.json` стоит `altered_content: true`).

## Что дальше

- Автосбор источников: RSS, транскрипты YouTube, Reddit.
- Отбор тем нейросетью и очередь на 3 ролика в день.
- Автозагрузка через YouTube Data API, потом TikTok, VK Клипы, Дзен.
- Обложки и статистика для калибровки крючков.
