"""Unit tests for pygamine.devtools.mp4_converter: video -> .jpg frames +
meta.yaml + .ogg audio, the input ImageSequenceMedia plays. Each test
renders a tiny real video with moviepy (from the `video` extra / dev group).
"""

from __future__ import annotations

import pytest
import yaml

moviepy = pytest.importorskip("moviepy")

from pygamine.devtools.mp4_converter import export_files, main  # noqa: E402

# moviepy's frame reader trips a NumPy 2.5 deprecation on every frame --
# its problem to fix, and pure noise in this suite's output.
pytestmark = pytest.mark.filterwarnings(
    "ignore:Setting the shape on a NumPy array:DeprecationWarning"
)


@pytest.fixture(scope="module")
def video(tmp_path_factory):
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
