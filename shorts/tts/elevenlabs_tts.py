from __future__ import annotations

import base64
import subprocess

import httpx

from ..ffmpeg import ffmpeg_exe
from ..models import TTSResult, WordTiming


class ElevenLabsTTS:
    """ElevenLabs: самые естественные голоса, платно (есть бесплатные 10 тысяч символов в месяц).
    Эндпоинт with-timestamps отдаёт посимвольные тайминги, из них собираются слова, whisper не нужен.
    Voice ID берётся в библиотеке голосов ElevenLabs (Voices -> выбрать голос -> ID).
    """

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model_id: str = "eleven_multilingual_v2",
        stability: float = 0.45,
        similarity: float = 0.8,
        style: float = 0.3,
        speed: float = 1.05,
        client: httpx.Client | None = None,
    ):
        if not api_key or not voice_id:
            raise ValueError("Для elevenlabs нужны ELEVENLABS_API_KEY и ELEVENLABS_VOICE_ID")
        self.api_key = api_key
        self.voice_id = voice_id
        self.model_id = model_id
        self.voice_settings = {
            "stability": stability,
            "similarity_boost": similarity,
            "style": style,
            "use_speaker_boost": True,
            "speed": speed,
        }
        self.client = client or httpx.Client(timeout=180.0)

    def synthesize(self, text: str, wav_path: str) -> TTSResult:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/with-timestamps"
        payload = {
            "text": text,
            "model_id": self.model_id,
            "output_format": "mp3_44100_128",
            "voice_settings": self.voice_settings,
        }
        headers = {"xi-api-key": self.api_key, "Content-Type": "application/json"}
        resp = self.client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"ElevenLabs {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
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
