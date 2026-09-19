import subprocess

from shorts.ffmpeg import ffmpeg_exe, media_duration
from shorts.videogen.assemble import assemble_clips
from shorts.videogen.wan_local import PRESETS, WanLocal


def make_clip(path, seconds, size="480x832"):
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-t", str(seconds), "-i", f"testsrc2=size={size}:rate=16",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)


def test_assemble_matches_segment_durations(tmp_path):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    make_clip(a, 3.0)
    make_clip(b, 5.0)
    out = tmp_path / "bg.mp4"
    # первый клип короче нужного (держим кадр), второй длиннее (режем)
    assemble_clips([(str(a), 4.5), (str(b), 3.2)], str(out), 540, 960, fps=30)
    assert abs(media_duration(str(out)) - 7.7) < 0.15


def test_frames_for_is_4k_plus_1():
    gen = WanLocal("wan21-1.3b")
    for sec in (1, 3, 5, 9):
        n = gen.frames_for(sec)
        assert (n - 1) % 4 == 0 and 17 <= n <= PRESETS["wan21-1.3b"].max_frames
    assert gen.frames_for(5) == 81
    assert WanLocal("wan22-5b").frames_for(5) == 121
