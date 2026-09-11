from __future__ import annotations

from ..config import Settings
from .base import LLM


def get_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "ollama":
        from .ollama_llm import OllamaLLM

        return OllamaLLM(settings.ollama_url, settings.ollama_model)
    if settings.llm_provider == "anthropic":
        from .anthropic_llm import AnthropicLLM

        return AnthropicLLM(settings.anthropic_model, settings.anthropic_api_key or None)
    raise ValueError(f"Неизвестный LLM_PROVIDER: {settings.llm_provider}")
