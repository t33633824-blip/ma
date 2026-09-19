from pathlib import Path

from shorts.config import Settings


def test_paths_follow_data_dir_unless_explicit():
    s = Settings(_env_file=None, data_dir=Path("/data/x"), out_dir=Path("/elsewhere/out"))
    assert s.piper_dir == Path("/data/x/models/piper")
    assert s.clips_dir == Path("/data/x/assets/clips")
    assert s.gameplay_dir == Path("/data/x/assets/gameplay")
    assert s.video_models_dir == Path("/data/x/models/video")
    assert s.out_dir == Path("/elsewhere/out")  # явно заданный путь не трогаем
    assert s.hf_home == Path("/data/x/models/hf")


def test_default_data_dir_keeps_relative_paths():
    s = Settings(_env_file=None)
    assert s.piper_dir == Path("models/piper") and s.out_dir == Path("out")


def test_data_move_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "models/piper").mkdir(parents=True)
    (tmp_path / "models/piper/voice.onnx").write_bytes(b"x")
    (tmp_path / "out/2026-01").mkdir(parents=True)
    (tmp_path / ".env").write_text("TTS_PROVIDER=edge\n", encoding="utf-8")
    target = tmp_path / "disk" / "data"

    from shorts.cli import main

    assert main(["data", "move", str(target)]) == 0
    assert (target / "models/piper/voice.onnx").exists()
    assert (target / "out/2026-01").exists()
    assert not (tmp_path / "models").exists()
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "TTS_PROVIDER=edge" in env and f"DATA_DIR={target}" in env

    monkeypatch.setenv("DATA_DIR", str(target))
    s = Settings(_env_file=None)
    assert s.piper_dir == target / "models/piper"
