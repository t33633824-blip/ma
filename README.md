# Shorts Pipeline

Автоматический конвейер вертикальных роликов: западная статья → пересказ на русском своими словами →
озвучка → субтитры по словам → готовый MP4 9:16 с геймплеем на фоне.

Роли разделены:

- **Куратор** (Claude с веб-поиском) ищет свежие материалы в RSS-лентах и в интернете, отбирает темы и кладёт их в очередь.
- **Автор** (локальная модель через Ollama) пишет сценарий, описание и теги. Piper озвучивает, faster-whisper снимает тайминги.

Любую роль можно переключить в `.env`: куратора на Ollama (тогда только RSS, без поиска), автора на Claude, голос на edge-tts или ElevenLabs.

## Быстрый старт

Одной командой (поставит uv, Python 3.12, зависимости, голос, проверит окружение):

```bash
git clone -b claude/quirky-archimedes-aj5n40 https://github.com/t33633824-blip/ma.git shorts
cd shorts
bash install.sh
nano .env            # впиши ANTHROPIC_API_KEY
./shorts.sh doctor
```

Дальше все команды через `./shorts.sh …`, активировать окружение не нужно.
Автопилот для cron: `autopilot.sh 3` делает `discover` и три ролика.

Ручная установка, если хочется по шагам:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 1. Локальная нейросеть для сценариев
#    https://ollama.com  → ollama pull qwen2.5:7b
# 2. Русский голос Piper (один раз, ~60 МБ)
python -m piper.download_voices --download-dir models/piper ru_RU-irina-medium
# 3. Фоновые видео в assets/gameplay/ — любой из трёх способов:
python -m shorts backgrounds generate --minutes 3 --count 3   # нарисовать залипательную анимацию (без чужих прав)
python -m shorts backgrounds fetch --query satisfying --count 10   # бесплатные стоковые с Pexels (нужен PEXELS_API_KEY)
#    или свои записи геймплея (см. assets/gameplay/README.md)

cp .env.example .env      # впиши ANTHROPIC_API_KEY для куратора, поправь тему канала
python -m shorts doctor   # проверит, что всё на месте

python -m shorts discover        # куратор: RSS + веб-поиск → 5 тем в queue.json
python -m shorts queue           # посмотреть очередь
python -m shorts run --count 3   # автор + озвучка + рендер по трём лучшим темам
python -m shorts make https://example.com/some-article   # или один ролик по конкретной ссылке
```

Для полного автопилота повесь в cron раз в день `discover`, затем `run --count 3`.

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
feeds.py     ─ RSS-ленты из feeds.txt: свежие записи, без дублей
curator.py   ─ куратор: Claude ищет в интернете и ранжирует кандидатов (или Ollama только ранжирует)
queue.py     ─ очередь тем в queue.json, она же история: сделанное не предлагается снова
sources.py   ─ скачать статью, вычистить меню и рекламу (trafilatura)
llm/         ─ сценарий по строгой JSON-схеме: Ollama (локально) или Claude
tts/         ─ голос: Piper (локально), edge-tts (бесплатно, облако), ElevenLabs (платно)
align.py     ─ тайминги слов: faster-whisper слушает озвучку, слова сценария получают время
subtitles.py ─ ASS-субтитры по 3 слова, текущее слово подсвечено
backgrounds.py─ генератор анимации «шарики в кольце» и загрузчик стоковых роликов с Pexels
background.py─ случайный фрагмент случайного файла из assets/gameplay
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

- `CURATOR_PROVIDER=anthropic|ollama`, `CURATOR_WEB_SEARCH`, `CURATOR_DAYS`, `CURATOR_PICKS`, `FEEDS_FILE`
- `WRITER_PROVIDER=ollama|anthropic`, `OLLAMA_MODEL` (для русского хорошо `qwen2.5:7b`, `qwen2.5:14b`, `gemma3:12b`)
- `TTS_PROVIDER=piper|edge|elevenlabs`
- `CHANNEL_TOPIC`, `CHANNEL_STYLE`, `TARGET_SECONDS` задают тон и длину сценария
- `SUBTITLE_WORDS_PER_LINE`, `SUBTITLE_FONT`

## Правила, чтобы канал жил долго

- Ролик это пересказ своими словами, а не перевод и не копия. В описании указан источник.
- Фон только из собственного или разрешённого издателем геймплея, без музыки из игры. Фильмы не использовать.
- При загрузке отмечать «изменённый или синтетический контент» (в `meta.json` стоит `altered_content: true`).

## Что дальше

- Транскрипты YouTube и Reddit как дополнительные источники для куратора.
- Автозагрузка через YouTube Data API, потом TikTok, VK Клипы, Дзен.
- Обложки и статистика для калибровки крючков.
