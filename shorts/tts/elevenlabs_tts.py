from __future__ import annotations

import base64
import subprocess

import httpx

from ..ffmpeg import ffmpeg_exe
from ..models import TTSResult, WordTiming


class ElevenLabsTTS:
    """Платная облачная озвучка. Использует эндпоинт with-timestamps и собирает слова из посимвольных таймингов.
    Не проверялось на реальном ключе: при первом запуске сверься с https://elevenlabs.io/docs
    """

    def __init__(self, api_key: str, voice_id: str, model_id: str = "eleven_multilingual_v2"):
        if not api_key or not voice_id:
            raise ValueError("Для elevenlabs нужны ELEVENLABS_API_KEY и ELEVENLABS_VOICE_ID")
        self.api_key = api_key
        self.voice_id = voice_id
        self.model_id = model_id

    def synthesize(self, text: str, wav_path: str) -> TTSResult:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/with-timestamps"
        payload = {"text": text, "model_id": self.model_id}
        headers = {"xi-api-key": self.api_key}
        with httpx.Client(timeout=120.0) as client:
            data = client.post(url, json=payload, headers=headers).raise_for_status().json()
        mp3_path = wav_path.rsplit(".", 1)[0] + ".mp3"
        with open(mp3_path, "wb") as f:
            f.write(base64.b64decode(data["audio_base64"]))
        subprocess.run(
            [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", mp3_path, "-ar", "24000", "-ac", "1", wav_path],
            check=True,
        )
        align = data.get("alignment") or {}
        words = chars_to_words(
            align.get("characters", []),
            align.get("character_start_times_seconds", []),
            align.get("character_end_times_seconds", []),
        )
        return TTSResult(wav_path=wav_path, words=words)


def chars_to_words(chars: list[str], starts: list[float], ends: list[float]) -> list[WordTiming]:
    words: list[WordTiming] = []
    buf: list[str] = []
    w_start = 0.0
    w_end = 0.0
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if buf:
                words.append(WordTiming("".join(buf), w_start, w_end))
                buf = []
            continue
        if not buf:
            w_start = s
        buf.append(ch)
        w_end = e
    if buf:
        words.append(WordTiming("".join(buf), w_start, w_end))
    return words
