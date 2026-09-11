from __future__ import annotations

import json

import httpx

from ..config import Settings
from ..models import Script, SourceDoc
from . import base


class OllamaLLM:
    """Локальная модель через Ollama (https://ollama.com). Структурированный вывод по JSON-схеме."""

    def __init__(self, base_url: str, model: str, timeout: float = 600.0, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client = client  # для тестов можно подсунуть клиент с MockTransport

    def _http(self) -> httpx.Client:
        return self._client or httpx.Client(timeout=self.timeout)

    def complete_json(self, system: str, user: str, schema: dict, temperature: float = 0.7) -> dict:
        payload = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "options": {"temperature": temperature, "num_ctx": 16384},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        resp = self._http().post(f"{self.base_url}/api/chat", json=payload)
        resp.raise_for_status()
        return json.loads(resp.json()["message"]["content"])

    def generate_script(self, doc: SourceDoc, settings: Settings) -> Script:
        return base.generate_script(self, doc, settings)

    def is_available(self) -> bool:
        try:
            self._http().get(f"{self.base_url}/api/tags").raise_for_status()
            return True
        except httpx.HTTPError:
            return False
