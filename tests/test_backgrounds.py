import json

import httpx

from shorts.backgrounds import best_portrait_file, fetch_pexels

VIDEO = {
    "id": 42,
    "duration": 30,
    "user": {"name": "Someone"},
    "video_files": [
        {"file_type": "video/mp4", "width": 1080, "height": 1920, "link": "https://cdn/x/1080.mp4"},
        {"file_type": "video/mp4", "width": 720, "height": 1280, "link": "https://cdn/x/720.mp4"},
        {"file_type": "video/mp4", "width": 1920, "height": 1080, "link": "https://cdn/x/landscape.mp4"},
    ],
}


def test_best_portrait_file_prefers_tallest_portrait():
    assert best_portrait_file(VIDEO)["link"] == "https://cdn/x/1080.mp4"
    assert best_portrait_file({"video_files": []}) is None


def test_fetch_pexels_downloads_and_skips_short(tmp_path):
    short = dict(VIDEO, id=7, duration=5)

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "api.pexels.com":
            assert req.headers["Authorization"] == "KEY"
            assert req.url.params["orientation"] == "portrait"
            page = int(req.url.params["page"])
            return httpx.Response(200, json={"videos": [short, VIDEO] if page == 1 else []})
        return httpx.Response(200, content=b"MP4DATA")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    saved = fetch_pexels("satisfying", 3, "KEY", tmp_path, client=client)
    assert [p.name for p in saved] == ["pexels-42.mp4"]
    assert (tmp_path / "pexels-42.mp4").read_bytes() == b"MP4DATA"
