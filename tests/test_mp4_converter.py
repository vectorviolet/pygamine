"""Unit tests for pygamine.devtools.mp4_converter: video -> .jpg frames +
meta.yaml + .ogg audio, the input ImageSequenceMedia plays. Each test
renders a tiny real video with moviepy (from the `video` extra / dev group).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

moviepy = pytest.importorskip("moviepy")

from pygamine.devtools.mp4_converter import (  # noqa: E402
    _export_audio,
    _export_frames,
    _prepare_frames_dir,
    _write_meta,
    export_files,
    main,
)

# moviepy's frame reader trips a NumPy 2.5 deprecation on every frame --
# its problem to fix, and pure noise in this suite's output.
pytestmark = pytest.mark.filterwarnings(
    "ignore:Setting the shape on a NumPy array:DeprecationWarning"
)


@pytest.fixture(scope="module")
def video(tmp_path_factory) -> Path:
    """1 s, 12 fps, 32x16 red clip with a sine-tone audio track."""
    import numpy as np

    path = tmp_path_factory.mktemp("video") / "intro.mp4"
    audio = moviepy.AudioClip(
        lambda t: np.sin(2 * np.pi * 440 * t), duration=1, fps=22050
    )
    clip = (
        moviepy.ColorClip((32, 16), color=(200, 30, 30), duration=1)
        .with_fps(12)
        .with_audio(audio)
    )
    clip.write_videofile(str(path), codec="libx264", audio_codec="aac", logger=None)
    return path


def test_writes_numbered_jpg_frames_meta_and_audio(video, tmp_path):
    count = export_files(video, tmp_path)

    frames = sorted((tmp_path / "frames").glob("*.jpg"))
    assert count == len(frames) == 12
    assert frames[0].name == "0001.jpg"
    assert (tmp_path / "intro_audio.ogg").is_file()

    meta = yaml.safe_load(
        (tmp_path / "frames" / "meta.yaml").read_text(encoding="utf-8")
    )
    assert meta == {"fps": 12, "frame_count": 12, "size": [32, 16]}


def test_rerun_clears_stale_frames_but_not_other_files(video, tmp_path):
    (tmp_path / "frames").mkdir()
    (tmp_path / "frames" / "0099.jpg").write_text("")
    (tmp_path / "keep_me.txt").write_text("")

    export_files(video, tmp_path)

    assert not (tmp_path / "frames" / "0099.jpg").exists()
    assert (tmp_path / "keep_me.txt").exists()


def test_missing_video_exits_with_a_message(tmp_path):
    with pytest.raises(SystemExit, match="Video not found"):
        export_files(tmp_path / "nope.mp4", tmp_path / "out")


def test_main_takes_video_and_output_arguments(video, tmp_path):
    main([str(video), "-o", str(tmp_path / "out")])
    assert (tmp_path / "out" / "frames" / "meta.yaml").is_file()


def test_main_prompts_when_no_arguments(video, tmp_path, monkeypatch):
    answers = iter([f'"{video}"', str(tmp_path / "prompted")])  # quotes are stripped
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    main([])

    assert (tmp_path / "prompted" / "frames" / "0001.jpg").is_file()


# ── helpers, with a fake clip (no video decoding) ───────────────────────


class _FakeAudio:
    def __init__(self, fail=False):
        self.fail = fail
        self.written = []

    def write_audiofile(self, path, **kwargs):
        if self.fail:
            raise OSError("no encoder")
        self.written.append((path, kwargs["codec"]))


class _FakeClip:
    fps = 12.0
    size = (32, 16)

    def __init__(self, frames=3, audio=None):
        self._frames = frames
        self.audio = audio

    def iter_frames(self, dtype):
        import numpy as np

        for _ in range(self._frames):
            yield np.zeros((16, 32, 3), dtype=dtype)


def test_prepare_frames_dir_returns_an_empty_frames_folder(tmp_path):
    (tmp_path / "frames").mkdir()
    (tmp_path / "frames" / "0099.jpg").write_text("")

    frames_dir = _prepare_frames_dir(tmp_path)

    assert frames_dir == tmp_path / "frames"
    assert list(frames_dir.iterdir()) == []


def test_export_audio_writes_the_track(tmp_path):
    audio = _FakeAudio()
    _export_audio(_FakeClip(audio=audio), tmp_path / "a.ogg")
    assert audio.written == [(str(tmp_path / "a.ogg"), "libvorbis")]


def test_export_audio_without_a_track_is_a_no_op(tmp_path):
    _export_audio(_FakeClip(audio=None), tmp_path / "a.ogg")


def test_export_audio_reports_a_failure_and_carries_on(tmp_path, capsys):
    _export_audio(_FakeClip(audio=_FakeAudio(fail=True)), tmp_path / "a.ogg")
    assert "Error producing sound: no encoder" in capsys.readouterr().out


def test_export_frames_numbers_the_jpgs_from_one(tmp_path):
    assert _export_frames(_FakeClip(frames=3), tmp_path) == 3
    assert [f.name for f in sorted(tmp_path.glob("*.jpg"))] == [
        "0001.jpg",
        "0002.jpg",
        "0003.jpg",
    ]


def test_write_meta_records_fps_count_and_size(tmp_path):
    _write_meta(tmp_path, _FakeClip(), 3)
    meta = yaml.safe_load((tmp_path / "meta.yaml").read_text(encoding="utf-8"))
    assert meta == {"fps": 12, "frame_count": 3, "size": [32, 16]}
