from __future__ import annotations

import asyncio
import subprocess

from ..ffmpeg import ffmpeg_exe
from ..models import TTSResult, WordTiming


class EdgeTTS:
    """Бесплатная облачная озвучка Microsoft. Отдаёт границы слов сама, whisper не нужен."""

    def __init__(self, voice: str, rate: str = "+0%", pitch: str = "+0Hz"):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    def synthesize(self, text: str, wav_path: str) -> TTSResult:
        mp3_path = wav_path.rsplit(".", 1)[0] + ".mp3"
        words = asyncio.run(self._run(text, mp3_path))
        subprocess.run(
            [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", mp3_path, "-ar", "24000", "-ac", "1", wav_path],
            check=True,
        )
        return TTSResult(wav_path=wav_path, words=words)

    async def _run(self, text: str, mp3_path: str) -> list[WordTiming]:
        import edge_tts

        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch, boundary="WordBoundary")
        words: list[WordTiming] = []
        with open(mp3_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start = chunk["offset"] / 10_000_000  # единицы по 100 нс
                    end = start + chunk["duration"] / 10_000_000
                    words.append(WordTiming(chunk["text"], start, end))
        return words
