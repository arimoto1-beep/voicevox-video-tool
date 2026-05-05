from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoLayout:
    name: str
    width: int
    height: int
    fps: int


@dataclass
class VideoOptions:
    audio_path: Path
    background_path: Path
    output_path: Path
    layout: str = "short"
    ffmpeg_path: str = "ffmpeg"


def get_video_layout(name: str) -> VideoLayout:
    if name == "short":
        return VideoLayout(name="short", width=1080, height=1920, fps=30)
    if name == "normal":
        return VideoLayout(name="normal", width=1920, height=1080, fps=30)
    raise ValueError(f"unknown layout: {name}")


def build_cover_filter(layout: VideoLayout) -> str:
    return (
        f"scale={layout.width}:{layout.height}:force_original_aspect_ratio=increase,"
        f"crop={layout.width}:{layout.height},"
        "setsar=1"
    )


def build_ffmpeg_command(options: VideoOptions, layout: VideoLayout) -> list[str]:
    return [
        options.ffmpeg_path,
        "-y",
        "-loop",
        "1",
        "-i",
        str(options.background_path),
        "-i",
        str(options.audio_path),
        "-vf",
        build_cover_filter(layout),
        "-r",
        str(layout.fps),
        "-c:v",
        "libx264",
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-pix_fmt",
        "yuv420p",
        "-shortest",
        str(options.output_path),
    ]


def run_ffmpeg(command: list[str]) -> None:
    subprocess.run(command, check=True)


def generate_video(options: VideoOptions) -> None:
    layout = get_video_layout(options.layout)
    command = build_ffmpeg_command(options, layout)
    options.output_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(command)


def parse_args(argv: list[str] | None = None) -> VideoOptions:
    parser = argparse.ArgumentParser(description="Generate an mp4 from a background image and audio.")
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--background", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--layout", choices=["short", "normal"], default="short")
    parser.add_argument("--ffmpeg", default="ffmpeg")

    args = parser.parse_args(argv)
    return VideoOptions(
        audio_path=args.audio,
        background_path=args.background,
        output_path=args.output,
        layout=args.layout,
        ffmpeg_path=args.ffmpeg,
    )


def main(argv: list[str] | None = None) -> int:
    try:
        options = parse_args(argv)
        generate_video(options)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"video_path={options.output_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
