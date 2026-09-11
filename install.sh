#!/usr/bin/env bash
# Установка одной командой: bash install.sh
# Ставит uv, отдельный Python 3.12, зависимости, русский голос и проверяет окружение.
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

say "1/6 Менеджер uv"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
uv --version

say "2/6 Python 3.12 в .venv"
if [ -x .venv/bin/python ] && .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info[:2]==(3,12) else 1)'; then
  echo "уже есть"
else
  rm -rf .venv
  uv venv --python 3.12 .venv
fi

say "3/6 Зависимости"
uv pip install --python .venv/bin/python -e ".[dev]"

say "4/6 Файл настроек .env"
if [ -f .env ]; then
  echo ".env уже есть, не трогаю"
else
  cp .env.example .env
  echo "создан .env из шаблона, впиши в него ANTHROPIC_API_KEY"
fi

say "5/6 Русский голос Piper"
VOICE=$(grep -E '^PIPER_VOICE=' .env | cut -d= -f2- || true)
VOICE=${VOICE:-ru_RU-irina-medium}
if [ -f "models/piper/$VOICE.onnx" ]; then
  echo "уже скачан"
else
  mkdir -p models/piper
  .venv/bin/python -m piper.download_voices --download-dir models/piper "$VOICE"
fi

say "6/6 Ollama"
if command -v ollama >/dev/null 2>&1; then
  MODEL=$(grep -E '^OLLAMA_MODEL=' .env | cut -d= -f2- || true)
  MODEL=${MODEL:-qwen2.5:7b}
  if ollama list 2>/dev/null | grep -q "^${MODEL%%:*}"; then
    echo "модель $MODEL есть"
  else
    echo "скачиваю модель $MODEL (несколько ГБ)…"
    ollama pull "$MODEL" || echo "не удалось скачать, проверь что Ollama запущена: ollama serve"
  fi
else
  echo "Ollama не установлена: https://ollama.com/download  (curl -fsSL https://ollama.com/install.sh | sh)"
fi

say "Проверка"
.venv/bin/python -m shorts doctor || true

cat <<'MSG'

Готово. Дальше команды через ./shorts.sh, окружение активировать не нужно:
  ./shorts.sh backgrounds generate --minutes 3   # фон
  ./shorts.sh discover --count 3                  # куратор отбирает темы
  ./shorts.sh run --count 1                       # сделать ролик
  ./shorts.sh queue                               # очередь
MSG
