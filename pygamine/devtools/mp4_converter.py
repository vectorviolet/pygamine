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

JPG_QUALITY = 90


def export_files(video_path: str | Path, output_folder: str | Path) -> int:
    """Writes `frames/` (frames + meta.yaml) and the audio into
    output_folder. Returns the number of frames written."""
    try:
        from moviepy import VideoFileClip
        from PIL import Image
    except ImportError as e:
        raise SystemExit(
            "pygamine-mp4-converter needs moviepy -- run it as: "
            "uv run --with moviepy pygamine-mp4-converter ..."
        ) from e

    path = Path(video_path)
    if not path.is_file():
        raise SystemExit(f"Video not found: {path}")
    out_dir = Path(output_folder)
    frames_dir = out_dir / "frames"

    # Clear frames from a previous run, so a shorter video leaves no stale frames behind
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)

    clip = VideoFileClip(str(path))
    try:
        # 1. Extracting audio from the video
        print("Exporting audio...")
        try:
            if clip.audio is not None:
                audio_out = out_dir / f"{path.stem}_audio.ogg"
                clip.audio.write_audiofile(
                    str(audio_out), codec="libvorbis", bitrate="128k", logger=None
                )
                print(f"Audio extracted: {audio_out.name}")
        except Exception as e:
            print(f"Error producing sound: {e}")

        # 2. Extracting frames from the video
        print("Exporting frames...")
        frame_count = 0
        for frame_count, frame in enumerate(clip.iter_frames(dtype="uint8"), start=1):
            # 0001.jpg, 0002.jpg
            frame_name = frames_dir / f"{frame_count:04d}.jpg"
            Image.fromarray(frame).convert("RGB").save(frame_name, quality=JPG_QUALITY)

        print(
            f"A total of {frame_count} frames have been successfully extracted at {clip.fps:g} fps."
        )

        # 3. Metadata for ImageSequenceMedia, which plays the frames at this fps
        width, height = clip.size
        (frames_dir / "meta.yaml").write_text(
            f"fps: {clip.fps:g}\n"
            f"frame_count: {frame_count}\n"
            f"size: [{width}, {height}]\n",
            encoding="utf-8",
        )
        print("Metadata written: frames/meta.yaml")
    finally:
        clip.close()
    return frame_count


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
