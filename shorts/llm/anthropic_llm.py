from __future__ import annotations

import json

import anthropic

from ..config import Settings
from ..models import Script, SourceDoc
from .base import build_prompts, script_json_schema


class AnthropicLLM:
    """Облачный вариант через Claude API. Включён server-side fallback на случай отказа классификатора."""

    def __init__(self, model: str, api_key: str | None = None):
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def generate_script(self, doc: SourceDoc, settings: Settings) -> Script:
        system, user = build_prompts(doc, settings)
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=4096,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": script_json_schema()}},
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Модель отказалась обрабатывать этот материал")
        text = next(block.text for block in response.content if block.type == "text")
        return Script.model_validate(json.loads(text))
