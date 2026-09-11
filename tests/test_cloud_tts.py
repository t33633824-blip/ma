import json
import wave

import httpx

from shorts.tts.elevenlabs_tts import ElevenLabsTTS
from shorts.tts.yandex_tts import YandexTTS, split_text


def test_split_text_by_sentences():
    text = "Раз два. Три четыре! Пять шесть? Семь."
    assert split_text(text, 15) == ["Раз два.", "Три четыре!", "Пять шесть?", "Семь."]
    assert split_text(text, 1000) == [text]


def test_yandex_writes_wav(tmp_path):
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers["Authorization"]
        seen["form"] = dict(httpx.QueryParams(req.content.decode()))
        return httpx.Response(200, content=b"\x00\x00" * 4800)  # 0.1 с тишины при 48 кГц

    tts = YandexTTS("KEY", voice="marina", emotion="friendly", speed=1.1, client=httpx.Client(transport=httpx.MockTransport(handler)))
    out = tmp_path / "v.wav"
    res = tts.synthesize("Привет мир.", str(out))
    assert res.words == []
    assert seen["auth"] == "Api-Key KEY"
    assert seen["form"]["voice"] == "marina" and seen["form"]["emotion"] == "friendly" and seen["form"]["format"] == "lpcm"
    with wave.open(str(out)) as w:
        assert w.getframerate() == 48000 and w.getnframes() == 4800


def test_elevenlabs_request_shape(tmp_path, monkeypatch):
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["key"] = req.headers["xi-api-key"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={
            "audio_base64": "AAAA",
            "alignment": {"characters": list("да"), "character_start_times_seconds": [0.0, 0.1], "character_end_times_seconds": [0.1, 0.2]},
        })

    # ffmpeg-конвертацию mp3 -> wav подменяем, тестируем только запрос и разбор ответа
    import shorts.tts.elevenlabs_tts as mod

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: None)
    tts = ElevenLabsTTS("KEY", "VOICE", client=httpx.Client(transport=httpx.MockTransport(handler)))
    res = tts.synthesize("да", str(tmp_path / "v.wav"))
    assert seen["url"].endswith("/v1/text-to-speech/VOICE/with-timestamps")
    assert seen["key"] == "KEY"
    assert seen["body"]["model_id"] == "eleven_multilingual_v2"
    assert seen["body"]["voice_settings"]["stability"] == 0.45
    assert [w.word for w in res.words] == ["да"]
