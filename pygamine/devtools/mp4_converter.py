"""Converts a video into what ImageSequenceMedia plays: numbered .jpg
frames plus a meta.yaml (fps, frame_count, size) in a `frames/` folder,
and the audio track as `<video name>_audio.ogg` next to it.

Installed as the `pygamine-mp4-converter` console script. Needs moviepy
(which bundles its own ffmpeg) -- the optional `video` extra -- so games
that only play sequences don't pull it in. From a game's repo root, add it
just for the run:

    uv run --with moviepy pygamine-mp4-converter intro.mp4 -o out

(or from pygamine's own repo: `uv run --extra video pygamine-mp4-converter`).

Without arguments it prompts for the video and output folder instead.
Copy `out/frames/` into a project's assets and register it under the
asset manifest's `sequences:`; meta.yaml carries the frame rate across.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

JPG_QUALITY = 90


def export_files(video_path: str | Path, output_folder: str | Path) -> int:
    """Writes `frames/` (frames + meta.yaml) and the audio into
    output_folder. Returns the number of frames written."""
    try:
        from moviepy import VideoFileClip
        from PIL import Image  # noqa: F401  # checked here, used by _export_frames
    except ImportError as e:
        raise SystemExit(
            "pygamine-mp4-converter needs moviepy -- run it as: "
            "uv run --with moviepy pygamine-mp4-converter ..."
        ) from e

    path = Path(video_path)
    if not path.is_file():
        raise SystemExit(f"Video not found: {path}")
    out_dir = Path(output_folder)
    frames_dir = _prepare_frames_dir(out_dir)

    clip = VideoFileClip(str(path))
    try:
        _export_audio(clip, out_dir / f"{path.stem}_audio.ogg")
        frame_count = _export_frames(clip, frames_dir)
        _write_meta(frames_dir, clip, frame_count)
    finally:
        clip.close()
    return frame_count


def _prepare_frames_dir(out_dir: Path) -> Path:
    """An empty `frames/` folder in `out_dir`. Frames from a previous run are
    cleared, so a shorter video leaves no stale frames behind."""
    frames_dir = out_dir / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)
    return frames_dir


def _export_audio(clip: Any, audio_out: Path) -> None:
    """Writes the clip's audio track to `audio_out`. A failure is reported
    and skipped -- the frames are still worth exporting."""
    print("Exporting audio...")
    try:
        if clip.audio is not None:
            clip.audio.write_audiofile(
                str(audio_out), codec="libvorbis", bitrate="128k", logger=None
            )
            print(f"Audio extracted: {audio_out.name}")
    except Exception as e:
        print(f"Error producing sound: {e}")


def _export_frames(clip: Any, frames_dir: Path) -> int:
    """Writes the clip's frames as 0001.jpg, 0002.jpg, ... into `frames_dir`.
    Returns the number of frames written."""
    from PIL import Image

    print("Exporting frames...")
    frame_count = 0
    for frame_count, frame in enumerate(clip.iter_frames(dtype="uint8"), start=1):
        frame_name = frames_dir / f"{frame_count:04d}.jpg"
        Image.fromarray(frame).convert("RGB").save(frame_name, quality=JPG_QUALITY)

    print(
        f"A total of {frame_count} frames have been successfully extracted at {clip.fps:g} fps."
    )
    return frame_count


def _write_meta(frames_dir: Path, clip: Any, frame_count: int) -> None:
    """Writes the meta.yaml ImageSequenceMedia reads, so the frames play at
    the video's fps."""
    width, height = clip.size
    (frames_dir / "meta.yaml").write_text(
        f"fps: {clip.fps:g}\nframe_count: {frame_count}\nsize: [{width}, {height}]\n",
        encoding="utf-8",
    )
    print("Metadata written: frames/meta.yaml")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="pygamine-mp4-converter",
        description="Convert a video into .jpg frames + meta.yaml + .ogg audio for ImageSequenceMedia.",
    )
    parser.add_argument(
        "video", nargs="?", help="video file to convert (prompted for if omitted)"
    )
    parser.add_argument("-o", "--output", help="output folder (default: out/)")
    args = parser.parse_args(argv)

    video = args.video or input("Enter the path to the video file: ")
    output = args.output or (
        "out/"
        if args.video
        else input("Enter the output directory for files (default: out/): ") or "out/"
    )
    export_files(video.strip("\"'"), output)


if __name__ == "__main__":
    main()
