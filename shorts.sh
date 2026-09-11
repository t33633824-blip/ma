#!/usr/bin/env bash
# Обёртка: ./shorts.sh <команда>. Сама использует .venv, активировать ничего не нужно.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Сначала запусти: bash install.sh" >&2
  exit 1
fi
exec .venv/bin/python -m shorts "$@"
