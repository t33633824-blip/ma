from __future__ import annotations

from typing import Protocol

from ..models import TTSResult


class TTS(Protocol):
    def synthesize(self, text: str, wav_path: str) -> TTSResult: ...
