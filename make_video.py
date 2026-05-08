from __future__ import annotations

import argparse
import re
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
    srt_path: Path | None = None
    ass_font_size: int | None = None
    ass_margin_v: int | None = None
    ass_wrap_chars: int | None = None
    ass_max_lines: int = 2


@dataclass(frozen=True)
class AssSubtitleStyle:
    font_name: str
    font_size: int
    margin_v: int
    outline: int
    shadow: int
    alignment: int = 2


@dataclass(frozen=True)
class SubtitleCue:
    start_sec: float
    end_sec: float
    text: str


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


def get_ass_subtitle_style(layout: VideoLayout) -> AssSubtitleStyle:
    if layout.name == "short":
        return AssSubtitleStyle(font_name="Yu Gothic UI", font_size=96, margin_v=260, outline=5, shadow=1)
    if layout.name == "normal":
        return AssSubtitleStyle(font_name="Yu Gothic UI", font_size=72, margin_v=150, outline=4, shadow=1)
    raise ValueError(f"unknown layout: {layout.name}")


def apply_ass_style_overrides(
    style: AssSubtitleStyle,
    font_size: int | None = None,
    margin_v: int | None = None,
) -> AssSubtitleStyle:
    if font_size is not None and font_size <= 0:
        raise ValueError("ASS font size must be greater than 0")
    if margin_v is not None and margin_v < 0:
        raise ValueError("ASS margin_v must be 0 or greater")

    return AssSubtitleStyle(
        font_name=style.font_name,
        font_size=font_size if font_size is not None else style.font_size,
        margin_v=margin_v if margin_v is not None else style.margin_v,
        outline=style.outline,
        shadow=style.shadow,
        alignment=style.alignment,
    )


def format_ass_time(seconds: float) -> str:
    if seconds < 0:
        raise ValueError("ASS timestamp cannot be negative")

    total_centiseconds = int(seconds * 100 + 0.5)
    total_seconds, centiseconds = divmod(total_centiseconds, 100)
    minutes, sec = divmod(total_seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours}:{minute:02}:{sec:02}.{centiseconds:02}"


def escape_ass_text(text: str) -> str:
    return text.replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def wrap_subtitle_text(
    text: str,
    wrap_chars: int | None = None,
    max_lines: int = 2,
) -> str:
    if max_lines <= 0:
        raise ValueError("ASS max lines must be greater than 0")
    if wrap_chars is None:
        return text
    if wrap_chars <= 0:
        raise ValueError("ASS wrap chars must be greater than 0")
    if text == "":
        return text

    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for source_line in normalized_text.split("\n"):
        if source_line == "":
            lines.append(source_line)
            continue
        lines.extend(source_line[index : index + wrap_chars] for index in range(0, len(source_line), wrap_chars))

    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + ["".join(lines[max_lines - 1 :])]

    return r"\N".join(lines)


def parse_srt_time(value: str) -> float:
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", value)
    if match is None:
        raise ValueError(f"invalid SRT timestamp: {value}")

    hours, minutes, seconds, milliseconds = (int(part) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def parse_srt_file(path: Path) -> list[SubtitleCue]:
    content = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    blocks = [block.strip() for block in re.split(r"\n\s*\n", content) if block.strip()]
    cues: list[SubtitleCue] = []

    for block in blocks:
        lines = block.split("\n")
        timing_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            raise ValueError(f"invalid SRT block: {block}")

        timing_parts = [part.strip() for part in lines[timing_index].split("-->")]
        if len(timing_parts) != 2:
            raise ValueError(f"invalid SRT timing line: {lines[timing_index]}")

        text_lines = lines[timing_index + 1 :]
        if not text_lines:
            raise ValueError(f"missing SRT text: {block}")

        start_sec = parse_srt_time(timing_parts[0])
        end_sec = parse_srt_time(timing_parts[1])
        if end_sec < start_sec:
            raise ValueError(f"SRT end time is before start time: {lines[timing_index]}")

        cues.append(SubtitleCue(start_sec=start_sec, end_sec=end_sec, text="\n".join(text_lines)))

    return cues


def build_ass_content(
    cues: list[SubtitleCue],
    layout: VideoLayout,
    style: AssSubtitleStyle,
    wrap_chars: int | None = None,
    max_lines: int = 2,
) -> str:
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {layout.width}",
        f"PlayResY: {layout.height}",
        "",
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
        ),
        (
            f"Style: Default,{style.font_name},{style.font_size},&H00FFFFFF,&H000000FF,"
            f"&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,{style.outline},"
            f"{style.shadow},{style.alignment},60,60,{style.margin_v},1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for cue in cues:
        display_text = wrap_subtitle_text(cue.text, wrap_chars=wrap_chars, max_lines=max_lines)
        lines.append(
            "Dialogue: "
            f"0,{format_ass_time(cue.start_sec)},{format_ass_time(cue.end_sec)},"
            f"Default,,0,0,0,,{escape_ass_text(display_text)}"
        )

    return "\n".join(lines) + "\n"


def write_ass_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def escape_path_for_ffmpeg_filter(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def build_ass_filter(ass_path: Path) -> str:
    return f"ass={escape_path_for_ffmpeg_filter(ass_path)}"


def build_video_filter(layout: VideoLayout, ass_path: Path | None = None) -> str:
    cover_filter = build_cover_filter(layout)
    if ass_path is None:
        return cover_filter
    return f"{cover_filter},{build_ass_filter(ass_path)}"


def build_ffmpeg_command(
    options: VideoOptions,
    layout: VideoLayout,
    ass_path: Path | None = None,
) -> list[str]:
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
        build_video_filter(layout, ass_path),
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
    options.output_path.parent.mkdir(parents=True, exist_ok=True)

    ass_path = None
    if options.srt_path is not None:
        cues = parse_srt_file(options.srt_path)
        style = get_ass_subtitle_style(layout)
        style = apply_ass_style_overrides(
            style,
            font_size=options.ass_font_size,
            margin_v=options.ass_margin_v,
        )
        ass_content = build_ass_content(
            cues,
            layout,
            style,
            wrap_chars=options.ass_wrap_chars,
            max_lines=options.ass_max_lines,
        )
        ass_path = options.output_path.with_suffix(".ass")
        write_ass_file(ass_path, ass_content)

    command = build_ffmpeg_command(options, layout, ass_path=ass_path)
    run_ffmpeg(command)


def parse_args(argv: list[str] | None = None) -> VideoOptions:
    parser = argparse.ArgumentParser(description="Generate an mp4 from a background image and audio.")
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--background", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--layout", choices=["short", "normal"], default="short")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--srt", type=Path)
    parser.add_argument("--ass-font-size", type=int)
    parser.add_argument("--ass-margin-v", type=int)
    parser.add_argument("--ass-wrap-chars", type=int)
    parser.add_argument("--ass-max-lines", type=int, default=2)

    args = parser.parse_args(argv)
    return VideoOptions(
        audio_path=args.audio,
        background_path=args.background,
        output_path=args.output,
        layout=args.layout,
        ffmpeg_path=args.ffmpeg,
        srt_path=args.srt,
        ass_font_size=args.ass_font_size,
        ass_margin_v=args.ass_margin_v,
        ass_wrap_chars=args.ass_wrap_chars,
        ass_max_lines=args.ass_max_lines,
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
