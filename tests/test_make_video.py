from pathlib import Path

import pytest

import make_video
from make_video import (
    VideoLayout,
    VideoOptions,
    build_cover_filter,
    build_ffmpeg_command,
    generate_video,
    get_video_layout,
    main,
    parse_args,
    run_ffmpeg,
)


def test_get_video_layout_returns_short_layout() -> None:
    layout = get_video_layout("short")

    assert layout == VideoLayout(name="short", width=1080, height=1920, fps=30)


def test_get_video_layout_returns_normal_layout() -> None:
    layout = get_video_layout("normal")

    assert layout == VideoLayout(name="normal", width=1920, height=1080, fps=30)


def test_get_video_layout_raises_for_unknown_layout() -> None:
    with pytest.raises(ValueError):
        get_video_layout("wide")


def test_build_cover_filter_returns_short_filter() -> None:
    layout = VideoLayout(name="short", width=1080, height=1920, fps=30)

    assert (
        build_cover_filter(layout)
        == "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    )


def test_build_cover_filter_returns_normal_filter() -> None:
    layout = VideoLayout(name="normal", width=1920, height=1080, fps=30)

    assert (
        build_cover_filter(layout)
        == "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1"
    )


def test_build_ffmpeg_command_builds_expected_arguments() -> None:
    options = VideoOptions(
        audio_path=Path("all.wav"),
        background_path=Path("background.png"),
        output_path=Path("output.mp4"),
        layout="short",
        ffmpeg_path="custom-ffmpeg",
    )
    layout = get_video_layout("short")

    command = build_ffmpeg_command(options, layout)

    assert command[0] == "custom-ffmpeg"
    assert "-y" in command
    assert command[command.index("-loop") + 1] == "1"

    input_indexes = [index for index, item in enumerate(command) if item == "-i"]
    assert command[input_indexes[0] + 1] == "background.png"
    assert command[input_indexes[1] + 1] == "all.wav"

    assert command[command.index("-vf") + 1] == build_cover_filter(layout)
    assert command[command.index("-r") + 1] == str(layout.fps)
    assert command[command.index("-c:v") + 1] == "libx264"
    assert command[command.index("-tune") + 1] == "stillimage"
    assert command[command.index("-c:a") + 1] == "aac"
    assert command[command.index("-b:a") + 1] == "192k"
    assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert "-shortest" in command
    assert command[-1] == "output.mp4"


def test_run_ffmpeg_calls_subprocess_run(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], bool]] = []

    def fake_run(command: list[str], *, check: bool) -> None:
        calls.append((command, check))

    monkeypatch.setattr(make_video.subprocess, "run", fake_run)

    command = ["ffmpeg", "-version"]
    run_ffmpeg(command)

    assert calls == [(command, True)]


def test_generate_video_creates_output_parent_and_runs_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def fake_run_ffmpeg(command: list[str]) -> None:
        commands.append(command)

    monkeypatch.setattr(make_video, "run_ffmpeg", fake_run_ffmpeg)
    options = VideoOptions(
        audio_path=Path("all.wav"),
        background_path=Path("background.png"),
        output_path=tmp_path / "nested" / "output.mp4",
    )

    generate_video(options)

    assert options.output_path.parent.is_dir()
    assert len(commands) == 1
    assert commands[0][-1] == str(options.output_path)


def test_generate_video_does_not_swallow_unknown_layout(tmp_path: Path) -> None:
    options = VideoOptions(
        audio_path=Path("all.wav"),
        background_path=Path("background.png"),
        output_path=tmp_path / "output.mp4",
        layout="unknown",
    )

    with pytest.raises(ValueError):
        generate_video(options)


def test_parse_args_builds_video_options_with_defaults() -> None:
    options = parse_args(
        [
            "--audio",
            "all.wav",
            "--background",
            "background.png",
            "--output",
            "output.mp4",
        ]
    )

    assert options == VideoOptions(
        audio_path=Path("all.wav"),
        background_path=Path("background.png"),
        output_path=Path("output.mp4"),
        layout="short",
        ffmpeg_path="ffmpeg",
    )


def test_parse_args_accepts_normal_layout_and_custom_ffmpeg() -> None:
    options = parse_args(
        [
            "--audio",
            "all.wav",
            "--background",
            "background.png",
            "--output",
            "output.mp4",
            "--layout",
            "normal",
            "--ffmpeg",
            "C:/tools/ffmpeg.exe",
        ]
    )

    assert options.layout == "normal"
    assert options.ffmpeg_path == "C:/tools/ffmpeg.exe"


def test_main_returns_zero_and_prints_video_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    options_seen: list[VideoOptions] = []

    def fake_generate_video(options: VideoOptions) -> None:
        options_seen.append(options)

    monkeypatch.setattr(make_video, "generate_video", fake_generate_video)

    exit_code = main(
        [
            "--audio",
            "all.wav",
            "--background",
            "background.png",
            "--output",
            "tmp/video/output.mp4",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert options_seen[0].output_path == Path("tmp/video/output.mp4")
    assert "video_path=tmp/video/output.mp4" in captured.out


def test_main_returns_one_and_prints_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_generate_video(options: VideoOptions) -> None:
        raise RuntimeError("ffmpeg failed")

    monkeypatch.setattr(make_video, "generate_video", fake_generate_video)

    exit_code = main(
        [
            "--audio",
            "all.wav",
            "--background",
            "background.png",
            "--output",
            "output.mp4",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error: ffmpeg failed" in captured.err
