from __future__ import annotations

import json

import anthropic

from ..config import Settings
from ..models import Script, SourceDoc
from . import base


class AnthropicLLM:
    """Облачный вариант через Claude API. Включён server-side fallback на случай отказа классификатора."""

    def __init__(self, model: str, api_key: str | None = None):
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def complete_json(self, system: str, user: str, schema: dict, temperature: float = 0.7) -> dict:
        # temperature на моделях 4.6+ не поддерживается, управляем только промптом
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=4096,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Модель отказалась обрабатывать этот материал")
        text = next(block.text for block in response.content if block.type == "text")
        return json.loads(text)

    def generate_script(self, doc: SourceDoc, settings: Settings) -> Script:
        return base.generate_script(self, doc, settings)
