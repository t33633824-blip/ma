from __future__ import annotations

import re
import wave

import httpx

from ..models import TTSResult

YANDEX_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"
MAX_CHARS = 4500  # лимит API 5000 символов на запрос


class YandexTTS:
    """Яндекс SpeechKit: одни из самых естественных русских голосов, доступен из России, оплата за символы.

    Ключ: Yandex Cloud -> сервисный аккаунт с ролью ai.speechkit-tts.user -> API-ключ.
    Голоса: marina, dasha, lera, masha, julia, jane (женские); kirill, anton, alexander, ermil, zahar, filipp (мужские).
    Тайминги слов сервис не отдаёт, их снимает faster-whisper.
    """

    def __init__(self, api_key: str, voice: str = "marina", emotion: str = "", speed: float = 1.05, client: httpx.Client | None = None):
        if not api_key:
            raise ValueError("Для yandex нужен YANDEX_API_KEY")
        self.api_key = api_key
        self.voice = voice
        self.emotion = emotion
        self.speed = speed
        self.sample_rate = 48000
        self.client = client or httpx.Client(timeout=120.0)

    def _synth_chunk(self, text: str) -> bytes:
        data = {
            "text": text,
            "lang": "ru-RU",
            "voice": self.voice,
            "speed": f"{self.speed:.2f}",
            "format": "lpcm",
            "sampleRateHertz": str(self.sample_rate),
        }
        if self.emotion:
            data["emotion"] = self.emotion
        resp = self.client.post(YANDEX_URL, data=data, headers={"Authorization": f"Api-Key {self.api_key}"})
        if resp.status_code != 200:
            raise RuntimeError(f"Yandex SpeechKit {resp.status_code}: {resp.text[:300]}")
        return resp.content

    def synthesize(self, text: str, wav_path: str) -> TTSResult:
        pcm = b"".join(self._synth_chunk(chunk) for chunk in split_text(text, MAX_CHARS))
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sample_rate)
            w.writeframes(pcm)
        return TTSResult(wav_path=wav_path, words=[])


def split_text(text: str, limit: int) -> list[str]:
    """Режет по предложениям так, чтобы каждый кусок был не длиннее limit символов."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    cur = ""
    for s in sentences:
        if not s:
            continue
        if cur and len(cur) + 1 + len(s) > limit:
            chunks.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return chunks or [text]
