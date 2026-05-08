from pathlib import Path

import pytest

import make_video
from make_video import (
    AssSubtitleStyle,
    SubtitleCue,
    VideoLayout,
    VideoOptions,
    apply_ass_style_overrides,
    build_ass_content,
    build_ass_filter,
    build_cover_filter,
    build_ffmpeg_command,
    build_video_filter,
    escape_ass_text,
    escape_path_for_ffmpeg_filter,
    format_ass_time,
    generate_video,
    get_ass_subtitle_style,
    get_video_layout,
    main,
    parse_args,
    parse_srt_file,
    parse_srt_time,
    run_ffmpeg,
    wrap_subtitle_text,
    write_ass_file,
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


def test_build_ffmpeg_command_uses_ass_video_filter_when_ass_path_is_given() -> None:
    options = VideoOptions(
        audio_path=Path("all.wav"),
        background_path=Path("background.png"),
        output_path=Path("output.mp4"),
    )
    layout = get_video_layout("short")

    command = build_ffmpeg_command(options, layout, ass_path=Path("tmp/video/output.ass"))

    assert command[command.index("-vf") + 1] == build_video_filter(layout, Path("tmp/video/output.ass"))
    assert "ass=tmp/video/output.ass" in command[command.index("-vf") + 1]


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


def test_get_ass_subtitle_style_returns_short_style() -> None:
    style = get_ass_subtitle_style(get_video_layout("short"))

    assert style == AssSubtitleStyle(
        font_name="Yu Gothic UI",
        font_size=96,
        margin_v=260,
        outline=5,
        shadow=1,
        alignment=2,
    )


def test_get_ass_subtitle_style_returns_normal_style() -> None:
    style = get_ass_subtitle_style(get_video_layout("normal"))

    assert style == AssSubtitleStyle(
        font_name="Yu Gothic UI",
        font_size=72,
        margin_v=150,
        outline=4,
        shadow=1,
        alignment=2,
    )


def test_apply_ass_style_overrides_keeps_style_when_values_are_not_given() -> None:
    style = get_ass_subtitle_style(get_video_layout("short"))

    assert apply_ass_style_overrides(style) == style


def test_apply_ass_style_overrides_replaces_font_size_only() -> None:
    style = get_ass_subtitle_style(get_video_layout("short"))

    updated = apply_ass_style_overrides(style, font_size=112)

    assert updated == AssSubtitleStyle(
        font_name="Yu Gothic UI",
        font_size=112,
        margin_v=260,
        outline=5,
        shadow=1,
        alignment=2,
    )


def test_apply_ass_style_overrides_replaces_margin_v_only() -> None:
    style = get_ass_subtitle_style(get_video_layout("short"))

    updated = apply_ass_style_overrides(style, margin_v=420)

    assert updated == AssSubtitleStyle(
        font_name="Yu Gothic UI",
        font_size=96,
        margin_v=420,
        outline=5,
        shadow=1,
        alignment=2,
    )


def test_apply_ass_style_overrides_replaces_font_size_and_margin_v() -> None:
    style = get_ass_subtitle_style(get_video_layout("normal"))

    updated = apply_ass_style_overrides(style, font_size=84, margin_v=180)

    assert updated == AssSubtitleStyle(
        font_name="Yu Gothic UI",
        font_size=84,
        margin_v=180,
        outline=4,
        shadow=1,
        alignment=2,
    )


def test_apply_ass_style_overrides_does_not_mutate_original_style() -> None:
    style = get_ass_subtitle_style(get_video_layout("short"))

    apply_ass_style_overrides(style, font_size=112, margin_v=420)

    assert style == AssSubtitleStyle(
        font_name="Yu Gothic UI",
        font_size=96,
        margin_v=260,
        outline=5,
        shadow=1,
        alignment=2,
    )


@pytest.mark.parametrize("font_size", [0, -1])
def test_apply_ass_style_overrides_raises_for_invalid_font_size(font_size: int) -> None:
    style = get_ass_subtitle_style(get_video_layout("short"))

    with pytest.raises(ValueError):
        apply_ass_style_overrides(style, font_size=font_size)


def test_apply_ass_style_overrides_raises_for_invalid_margin_v() -> None:
    style = get_ass_subtitle_style(get_video_layout("short"))

    with pytest.raises(ValueError):
        apply_ass_style_overrides(style, margin_v=-1)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0.0, "0:00:00.00"),
        (1.23, "0:00:01.23"),
        (61.5, "0:01:01.50"),
        (3661.234, "1:01:01.23"),
    ],
)
def test_format_ass_time_formats_seconds(seconds: float, expected: str) -> None:
    assert format_ass_time(seconds) == expected


def test_format_ass_time_raises_for_negative_seconds() -> None:
    with pytest.raises(ValueError):
        format_ass_time(-0.01)


def test_escape_ass_text_escapes_newline_and_braces() -> None:
    assert escape_ass_text("a\n{b}") == r"a\N\{b\}"


def test_wrap_subtitle_text_returns_original_when_wrap_chars_is_none() -> None:
    assert wrap_subtitle_text("音声と字幕をまとめて作る") == "音声と字幕をまとめて作る"


def test_wrap_subtitle_text_keeps_empty_text() -> None:
    assert wrap_subtitle_text("", wrap_chars=8) == ""


def test_wrap_subtitle_text_does_not_wrap_short_text() -> None:
    assert wrap_subtitle_text("短い字幕", wrap_chars=8) == "短い字幕"


def test_wrap_subtitle_text_inserts_ass_newline_when_wrap_chars_is_given() -> None:
    assert wrap_subtitle_text("音声と字幕をまとめて作る", wrap_chars=8) == r"音声と字幕をまと\Nめて作る"


def test_wrap_subtitle_text_keeps_max_two_lines() -> None:
    wrapped = wrap_subtitle_text("12345678901234567890", wrap_chars=5, max_lines=2)

    assert wrapped == r"12345\N678901234567890"
    assert len(wrapped.split(r"\N")) == 2


def test_wrap_subtitle_text_merges_remaining_text_into_last_line() -> None:
    assert wrap_subtitle_text("123456789012", wrap_chars=3, max_lines=3) == r"123\N456\N789012"


def test_wrap_subtitle_text_treats_existing_newline_as_ass_newline() -> None:
    assert wrap_subtitle_text("1行目\n2行目", wrap_chars=10) == r"1行目\N2行目"


@pytest.mark.parametrize("wrap_chars", [0, -1])
def test_wrap_subtitle_text_raises_for_invalid_wrap_chars(wrap_chars: int) -> None:
    with pytest.raises(ValueError):
        wrap_subtitle_text("text", wrap_chars=wrap_chars)


def test_wrap_subtitle_text_raises_for_invalid_max_lines() -> None:
    with pytest.raises(ValueError):
        wrap_subtitle_text("text", wrap_chars=4, max_lines=0)


def test_escape_ass_text_keeps_wrapped_ass_newline_and_escapes_braces() -> None:
    wrapped = wrap_subtitle_text("abcd{efgh}", wrap_chars=4)

    assert escape_ass_text(wrapped) == r"abcd\N\{efgh\}"


def test_parse_srt_time_converts_timestamp_to_seconds() -> None:
    assert parse_srt_time("00:00:01,230") == pytest.approx(1.23)
    assert parse_srt_time("01:02:03,456") == pytest.approx(3723.456)


def test_parse_srt_time_raises_for_invalid_format() -> None:
    with pytest.raises(ValueError):
        parse_srt_time("1:02:03.456")


def test_parse_srt_file_reads_cues(tmp_path: Path) -> None:
    srt_path = tmp_path / "output.srt"
    srt_path.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:01,500\n"
        "こんにちは\n"
        "\n"
        "2\n"
        "00:00:01,500 --> 00:00:03,000\n"
        "次の字幕\n",
        encoding="utf-8",
    )

    assert parse_srt_file(srt_path) == [
        SubtitleCue(start_sec=0.0, end_sec=1.5, text="こんにちは"),
        SubtitleCue(start_sec=1.5, end_sec=3.0, text="次の字幕"),
    ]


def test_parse_srt_file_keeps_multiline_text(tmp_path: Path) -> None:
    srt_path = tmp_path / "output.srt"
    srt_path.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:01,500\n"
        "1行目\n"
        "2行目\n",
        encoding="utf-8",
    )

    assert parse_srt_file(srt_path) == [
        SubtitleCue(start_sec=0.0, end_sec=1.5, text="1行目\n2行目"),
    ]


def test_parse_srt_file_raises_for_invalid_block(tmp_path: Path) -> None:
    srt_path = tmp_path / "output.srt"
    srt_path.write_text("1\ninvalid\ntext\n", encoding="utf-8")

    with pytest.raises(ValueError):
        parse_srt_file(srt_path)


def test_build_ass_content_builds_ass_sections_and_dialogues() -> None:
    layout = get_video_layout("short")
    style = get_ass_subtitle_style(layout)
    cues = [SubtitleCue(start_sec=0.0, end_sec=1.5, text="こんにちは\nテスト")]

    content = build_ass_content(cues, layout, style)

    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "[Events]" in content
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert "Style: Default,Yu Gothic UI,96," in content
    assert ",1,5,1,2,60,60,260,1" in content
    assert r"Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,こんにちは\Nテスト" in content


def test_build_ass_content_uses_normal_style_values() -> None:
    layout = get_video_layout("normal")
    style = get_ass_subtitle_style(layout)
    cues = [SubtitleCue(start_sec=0.0, end_sec=1.5, text="text")]

    content = build_ass_content(cues, layout, style)

    assert "Style: Default,Yu Gothic UI,72," in content
    assert ",1,4,1,2,60,60,150,1" in content


def test_build_ass_content_wraps_dialogue_text_when_wrap_chars_is_given() -> None:
    layout = get_video_layout("short")
    style = get_ass_subtitle_style(layout)
    cues = [SubtitleCue(start_sec=0.0, end_sec=1.5, text="音声と字幕をまとめて作る")]

    content = build_ass_content(cues, layout, style, wrap_chars=8, max_lines=2)

    assert r"Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,音声と字幕をまと\Nめて作る" in content


def test_build_ass_content_does_not_wrap_dialogue_text_when_wrap_chars_is_none() -> None:
    layout = get_video_layout("short")
    style = get_ass_subtitle_style(layout)
    cues = [SubtitleCue(start_sec=0.0, end_sec=1.5, text="音声と字幕をまとめて作る")]

    content = build_ass_content(cues, layout, style)

    assert r"音声と字幕をま\Nとめて作る" not in content
    assert "Default,,0,0,0,,音声と字幕をまとめて作る" in content


def test_write_ass_file_creates_parent_and_writes_utf8(tmp_path: Path) -> None:
    ass_path = tmp_path / "nested" / "output.ass"

    write_ass_file(ass_path, "こんにちは\n")

    assert ass_path.read_text(encoding="utf-8") == "こんにちは\n"


def test_escape_path_for_ffmpeg_filter_escapes_windows_path() -> None:
    escaped = escape_path_for_ffmpeg_filter(Path(r"C:\tmp\video's\output.ass"))

    assert escaped == r"C\:/tmp/video\'s/output.ass"


def test_build_ass_filter_returns_ass_filter() -> None:
    assert build_ass_filter(Path("tmp/video/output.ass")) == "ass=tmp/video/output.ass"


def test_build_video_filter_returns_cover_filter_without_ass() -> None:
    layout = get_video_layout("short")

    assert build_video_filter(layout) == build_cover_filter(layout)


def test_build_video_filter_appends_ass_filter() -> None:
    layout = get_video_layout("short")

    assert build_video_filter(layout, Path("tmp/video/output.ass")) == (
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,"
        "ass=tmp/video/output.ass"
    )


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
        srt_path=None,
        ass_font_size=None,
        ass_margin_v=None,
        ass_wrap_chars=None,
        ass_max_lines=2,
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


def test_parse_args_accepts_srt_path() -> None:
    options = parse_args(
        [
            "--audio",
            "all.wav",
            "--background",
            "background.png",
            "--output",
            "output.mp4",
            "--srt",
            "output.srt",
        ]
    )

    assert options.srt_path == Path("output.srt")


def test_parse_args_accepts_ass_style_overrides() -> None:
    options = parse_args(
        [
            "--audio",
            "all.wav",
            "--background",
            "background.png",
            "--output",
            "output.mp4",
            "--ass-font-size",
            "112",
            "--ass-margin-v",
            "420",
        ]
    )

    assert options.ass_font_size == 112
    assert options.ass_margin_v == 420


def test_parse_args_accepts_ass_wrap_options() -> None:
    options = parse_args(
        [
            "--audio",
            "all.wav",
            "--background",
            "background.png",
            "--output",
            "output.mp4",
            "--ass-wrap-chars",
            "14",
            "--ass-max-lines",
            "2",
        ]
    )

    assert options.ass_wrap_chars == 14
    assert options.ass_max_lines == 2


def test_generate_video_with_srt_writes_ass_and_runs_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def fake_run_ffmpeg(command: list[str]) -> None:
        commands.append(command)

    monkeypatch.setattr(make_video, "run_ffmpeg", fake_run_ffmpeg)
    srt_path = tmp_path / "output.srt"
    srt_path.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:01,500\n"
        "こんにちは\n",
        encoding="utf-8",
    )
    options = VideoOptions(
        audio_path=Path("all.wav"),
        background_path=Path("background.png"),
        output_path=tmp_path / "video" / "output.mp4",
        srt_path=srt_path,
    )

    generate_video(options)

    ass_path = options.output_path.with_suffix(".ass")
    assert ass_path.exists()
    assert "Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,こんにちは" in ass_path.read_text(
        encoding="utf-8"
    )
    assert len(commands) == 1
    assert f"ass={escape_path_for_ffmpeg_filter(ass_path)}" in commands[0][commands[0].index("-vf") + 1]


def test_generate_video_with_srt_applies_ass_style_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def fake_run_ffmpeg(command: list[str]) -> None:
        commands.append(command)

    monkeypatch.setattr(make_video, "run_ffmpeg", fake_run_ffmpeg)
    srt_path = tmp_path / "output.srt"
    srt_path.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:01,500\n"
        "こんにちは\n",
        encoding="utf-8",
    )
    options = VideoOptions(
        audio_path=Path("all.wav"),
        background_path=Path("background.png"),
        output_path=tmp_path / "video" / "output.mp4",
        srt_path=srt_path,
        ass_font_size=112,
        ass_margin_v=420,
    )

    generate_video(options)

    ass_path = options.output_path.with_suffix(".ass")
    content = ass_path.read_text(encoding="utf-8")
    assert "Style: Default,Yu Gothic UI,112," in content
    assert ",1,5,1,2,60,60,420,1" in content
    assert len(commands) == 1


def test_generate_video_with_srt_applies_ass_wrap_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def fake_run_ffmpeg(command: list[str]) -> None:
        commands.append(command)

    monkeypatch.setattr(make_video, "run_ffmpeg", fake_run_ffmpeg)
    srt_path = tmp_path / "output.srt"
    srt_path.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:01,500\n"
        "音声と字幕をまとめて作る\n",
        encoding="utf-8",
    )
    options = VideoOptions(
        audio_path=Path("all.wav"),
        background_path=Path("background.png"),
        output_path=tmp_path / "video" / "output.mp4",
        srt_path=srt_path,
        ass_wrap_chars=8,
        ass_max_lines=2,
    )

    generate_video(options)

    ass_path = options.output_path.with_suffix(".ass")
    content = ass_path.read_text(encoding="utf-8")
    assert r"Default,,0,0,0,,音声と字幕をまと\Nめて作る" in content
    assert len(commands) == 1


def test_generate_video_without_srt_does_not_write_ass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def fake_run_ffmpeg(command: list[str]) -> None:
        commands.append(command)

    monkeypatch.setattr(make_video, "run_ffmpeg", fake_run_ffmpeg)
    options = VideoOptions(
        audio_path=Path("all.wav"),
        background_path=Path("background.png"),
        output_path=tmp_path / "video" / "output.mp4",
        ass_font_size=112,
        ass_margin_v=420,
        ass_wrap_chars=8,
        ass_max_lines=2,
    )

    generate_video(options)

    assert not options.output_path.with_suffix(".ass").exists()
    assert commands[0][commands[0].index("-vf") + 1] == build_cover_filter(get_video_layout("short"))


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
