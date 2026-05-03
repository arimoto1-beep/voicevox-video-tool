from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request
import wave

import pytest

import make_voicevox_assets
from make_voicevox_assets import (
    DialogueEvent,
    ScriptParseError,
    ScriptEvent,
    SilenceEvent,
    SrtCue,
    SoundEffectEvent,
    VoicevoxApiError,
    WavInfo,
    attach_sound_effect_info,
    build_srt_cues,
    concatenate_wavs,
    create_audio_query,
    fetch_voicevox_speakers,
    insert_gap_events,
    parse_script,
    read_wav_info,
    read_script_file,
    resolve_speaker_id,
    synthesize_dialogue_wav,
    synthesize_dialogue_wavs,
    synthesize_wav,
    write_wav_bytes,
)


def _write_test_wav(
    path: Path,
    *,
    channels: int = 2,
    sample_width: int = 2,
    frame_rate: int = 8000,
    frame_count: int = 1600,
    frames: bytes | None = None,
) -> None:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(frame_rate)
        wav_file.writeframes(frames if frames is not None else b"\x00" * channels * sample_width * frame_count)


class _FakeHttpResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def test_read_script_file_reads_existing_file(tmp_path: Path) -> None:
    script_path = tmp_path / "script.txt"
    script_path.write_text("ずんだもん：こんにちは\nめたん：やあ\n", encoding="utf-8")

    assert read_script_file(script_path) == [
        "ずんだもん：こんにちは",
        "めたん：やあ",
    ]


def test_read_script_file_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_script_file(tmp_path / "missing.txt")


def test_read_script_file_keeps_blank_and_comment_lines(tmp_path: Path) -> None:
    script_path = tmp_path / "script.txt"
    script_path.write_text("ずんだもん：こんにちは\n\n# コメント\n", encoding="utf-8")

    assert read_script_file(script_path) == [
        "ずんだもん：こんにちは",
        "",
        "# コメント",
    ]


def test_parse_script_parses_full_width_colon_dialogue(tmp_path: Path) -> None:
    events = parse_script(["ずんだもん：こんにちは"], tmp_path)

    assert len(events) == 1
    assert isinstance(events[0], DialogueEvent)
    assert events[0].line_no == 1
    assert events[0].speaker == "ずんだもん"
    assert events[0].voice_text == "こんにちは"
    assert events[0].subtitle_text == "こんにちは"
    assert events[0].params == {}


def test_parse_script_parses_half_width_colon_dialogue(tmp_path: Path) -> None:
    events = parse_script(["ずんだもん:こんにちは"], tmp_path)

    assert len(events) == 1
    assert isinstance(events[0], DialogueEvent)
    assert events[0].speaker == "ずんだもん"
    assert events[0].voice_text == "こんにちは"


def test_parse_script_inherits_previous_speaker(tmp_path: Path) -> None:
    events = parse_script(["めたん：あーそれ", "印刷開始の振動でしょ"], tmp_path)

    assert len(events) == 2
    assert all(isinstance(event, DialogueEvent) for event in events)
    assert events[0].speaker == "めたん"
    assert events[1].speaker == "めたん"
    assert events[1].voice_text == "印刷開始の振動でしょ"


def test_parse_script_omitted_speaker_without_previous_speaker_raises(tmp_path: Path) -> None:
    with pytest.raises(ScriptParseError, match="1行目"):
        parse_script(["話者なしセリフ"], tmp_path)


def test_parse_script_splits_voice_text_and_subtitle_text(tmp_path: Path) -> None:
    events = parse_script(["めたん：あーそれ || あ、それ"], tmp_path)

    assert len(events) == 1
    assert isinstance(events[0], DialogueEvent)
    assert events[0].voice_text == "あーそれ"
    assert events[0].subtitle_text == "あ、それ"


def test_parse_script_parses_silence_event(tmp_path: Path) -> None:
    events = parse_script(["(間 0.25)"], tmp_path)

    assert events == [SilenceEvent(line_no=1, duration_sec=0.25, source="script")]


def test_parse_script_negative_silence_duration_raises(tmp_path: Path) -> None:
    with pytest.raises(ScriptParseError, match="1行目"):
        parse_script(["(間 -0.25)"], tmp_path)


def test_parse_script_parses_sound_effect_event(tmp_path: Path) -> None:
    events = parse_script([r"(SE se\pop.wav)"], tmp_path)

    assert len(events) == 1
    assert isinstance(events[0], SoundEffectEvent)
    assert events[0].line_no == 1
    assert events[0].path == tmp_path / Path(r"se\pop.wav")
    assert events[0].params == {}


def test_parse_script_ignores_blank_and_comment_lines(tmp_path: Path) -> None:
    events = parse_script(["", "   ", "# コメント", "ずんだもん：こんにちは"], tmp_path)

    assert len(events) == 1
    assert isinstance(events[0], DialogueEvent)
    assert events[0].line_no == 4


def test_parse_script_parses_dialogue_params(tmp_path: Path) -> None:
    events = parse_script(["めたん：原因はこれよ{speed=1.16, pause=0.9}"], tmp_path)

    assert len(events) == 1
    assert isinstance(events[0], DialogueEvent)
    assert events[0].params == {"speed": "1.16", "pause": "0.9"}


def test_parse_script_invalid_param_format_raises(tmp_path: Path) -> None:
    with pytest.raises(ScriptParseError, match="1行目"):
        parse_script(["めたん：こんにちは{speed}"], tmp_path)


def test_parse_script_parses_sound_effect_params(tmp_path: Path) -> None:
    events = parse_script([r"(SE se\whoosh.wav){volume=0.35, fade_in=0.01, fade_out=0.03}"], tmp_path)

    assert len(events) == 1
    assert isinstance(events[0], SoundEffectEvent)
    assert events[0].params == {
        "volume": "0.35",
        "fade_in": "0.01",
        "fade_out": "0.03",
    }


def test_parse_script_unsupported_dialogue_param_raises(tmp_path: Path) -> None:
    with pytest.raises(ScriptParseError, match="1行目"):
        parse_script(["めたん：こんにちは{volume=0.5}"], tmp_path)


def test_parse_script_unsupported_sound_effect_param_raises(tmp_path: Path) -> None:
    with pytest.raises(ScriptParseError, match="1行目"):
        parse_script([r"(SE se\pop.wav){speed=1.2}"], tmp_path)


def test_parse_script_empty_dialogue_text_raises(tmp_path: Path) -> None:
    with pytest.raises(ScriptParseError, match="1行目"):
        parse_script(["めたん："], tmp_path)


def test_parse_script_empty_voice_text_raises(tmp_path: Path) -> None:
    with pytest.raises(ScriptParseError, match="1行目"):
        parse_script(["めたん： || 字幕だけ"], tmp_path)


def test_parse_script_empty_subtitle_text_raises(tmp_path: Path) -> None:
    with pytest.raises(ScriptParseError, match="1行目"):
        parse_script(["めたん：読み上げだけ || "], tmp_path)


def test_insert_gap_events_inserts_gap_between_consecutive_dialogues() -> None:
    events = [
        DialogueEvent(1, "ずんだもん", "A", "A", {}),
        DialogueEvent(2, "めたん", "B", "B", {}),
        DialogueEvent(3, "ずんだもん", "C", "C", {}),
    ]

    result = insert_gap_events(events, 0.08)

    assert result == [
        events[0],
        SilenceEvent(line_no=None, duration_sec=0.08, source="gap"),
        events[1],
        SilenceEvent(line_no=None, duration_sec=0.08, source="gap"),
        events[2],
    ]


def test_insert_gap_events_does_not_insert_between_dialogue_and_silence() -> None:
    events = [
        DialogueEvent(1, "ずんだもん", "A", "A", {}),
        SilenceEvent(2, 0.25, "script"),
        DialogueEvent(3, "めたん", "B", "B", {}),
    ]

    assert insert_gap_events(events, 0.08) == events


def test_insert_gap_events_does_not_insert_between_dialogue_and_sound_effect(tmp_path: Path) -> None:
    events = [
        DialogueEvent(1, "ずんだもん", "A", "A", {}),
        SoundEffectEvent(2, tmp_path / "pop.wav", {}),
        DialogueEvent(3, "めたん", "B", "B", {}),
    ]

    assert insert_gap_events(events, 0.08) == events


def test_insert_gap_events_zero_gap_keeps_event_list_content() -> None:
    events = [
        DialogueEvent(1, "ずんだもん", "A", "A", {}),
        DialogueEvent(2, "めたん", "B", "B", {}),
    ]

    assert insert_gap_events(events, 0) == events


def test_insert_gap_events_empty_list_returns_empty_list() -> None:
    assert insert_gap_events([], 0.08) == []


def test_insert_gap_events_single_event_does_not_insert_gap() -> None:
    events = [DialogueEvent(1, "ずんだもん", "A", "A", {})]

    assert insert_gap_events(events, 0.08) == events


def test_insert_gap_events_negative_gap_raises() -> None:
    events = [DialogueEvent(1, "ずんだもん", "A", "A", {})]

    with pytest.raises(ValueError):
        insert_gap_events(events, -0.1)


def test_read_wav_info_reads_wav_format_info(tmp_path: Path) -> None:
    wav_path = tmp_path / "voice.wav"
    _write_test_wav(
        wav_path,
        channels=2,
        sample_width=2,
        frame_rate=8000,
        frame_count=1600,
    )

    assert read_wav_info(wav_path) == WavInfo(
        channels=2,
        sample_width=2,
        frame_rate=8000,
        frame_count=1600,
        duration_sec=0.2,
    )


def test_read_wav_info_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_wav_info(tmp_path / "missing.wav")


def test_read_wav_info_non_wav_file_raises_value_error(tmp_path: Path) -> None:
    not_wav_path = tmp_path / "not_wav.txt"
    not_wav_path.write_text("not a wav file", encoding="utf-8")

    with pytest.raises(ValueError, match="WAVファイルとして読み込めません"):
        read_wav_info(not_wav_path)


def test_read_wav_info_duration_is_frame_count_divided_by_frame_rate(tmp_path: Path) -> None:
    wav_path = tmp_path / "duration.wav"
    _write_test_wav(
        wav_path,
        channels=1,
        sample_width=1,
        frame_rate=44100,
        frame_count=22050,
    )

    info = read_wav_info(wav_path)

    assert info.duration_sec == 22050 / 44100


def test_fetch_voicevox_speakers_calls_speakers_api_and_returns_json(monkeypatch: pytest.MonkeyPatch) -> None:
    called_urls: list[str] = []

    def fake_urlopen(url: str, timeout: int) -> _FakeHttpResponse:
        called_urls.append(url)
        assert timeout == 10
        return _FakeHttpResponse(
            '[{"name": "四国めたん", "styles": [{"id": 2, "name": "ノーマル"}]}]'.encode("utf-8")
        )

    monkeypatch.setattr(make_voicevox_assets.urllib.request, "urlopen", fake_urlopen)

    speakers = fetch_voicevox_speakers("http://127.0.0.1:50021")

    assert called_urls == ["http://127.0.0.1:50021/speakers"]
    assert speakers == [{"name": "四国めたん", "styles": [{"id": 2, "name": "ノーマル"}]}]


def test_fetch_voicevox_speakers_handles_base_url_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    called_urls: list[str] = []

    def fake_urlopen(url: str, timeout: int) -> _FakeHttpResponse:
        called_urls.append(url)
        return _FakeHttpResponse(b"[]")

    monkeypatch.setattr(make_voicevox_assets.urllib.request, "urlopen", fake_urlopen)

    assert fetch_voicevox_speakers("http://127.0.0.1:50021/") == []
    assert called_urls == ["http://127.0.0.1:50021/speakers"]


def test_fetch_voicevox_speakers_connection_failure_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, timeout: int) -> _FakeHttpResponse:
        raise URLError("connection refused")

    monkeypatch.setattr(make_voicevox_assets.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(VoicevoxApiError, match="VOICEVOXに接続できません"):
        fetch_voicevox_speakers("http://127.0.0.1:50021")


def test_fetch_voicevox_speakers_http_error_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, timeout: int) -> _FakeHttpResponse:
        raise HTTPError(url, 500, "Internal Server Error", hdrs=None, fp=None)

    monkeypatch.setattr(make_voicevox_assets.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(VoicevoxApiError, match="HTTP 500"):
        fetch_voicevox_speakers("http://127.0.0.1:50021")


def test_fetch_voicevox_speakers_invalid_json_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, timeout: int) -> _FakeHttpResponse:
        return _FakeHttpResponse(b"not json")

    monkeypatch.setattr(make_voicevox_assets.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(VoicevoxApiError, match="JSONを解析できません"):
        fetch_voicevox_speakers("http://127.0.0.1:50021")


def test_resolve_speaker_id_returns_first_style_id_for_matching_speaker() -> None:
    speakers = [
        {"name": "四国めたん", "styles": [{"id": 2, "name": "ノーマル"}]},
        {"name": "ずんだもん", "styles": [{"id": 3, "name": "ノーマル"}]},
    ]

    assert resolve_speaker_id("ずんだもん", speakers, aliases={}) == 3


def test_resolve_speaker_id_resolves_speaker_alias() -> None:
    speakers = [{"name": "四国めたん", "styles": [{"id": 2, "name": "ノーマル"}]}]

    assert resolve_speaker_id("めたん", speakers, aliases={"めたん": "四国めたん"}) == 2


def test_resolve_speaker_id_missing_speaker_raises_voicevox_api_error() -> None:
    speakers = [{"name": "四国めたん", "styles": [{"id": 2, "name": "ノーマル"}]}]

    with pytest.raises(VoicevoxApiError, match="見つかりません"):
        resolve_speaker_id("ずんだもん", speakers, aliases={})


def test_resolve_speaker_id_empty_styles_raises_voicevox_api_error() -> None:
    speakers = [{"name": "ずんだもん", "styles": []}]

    with pytest.raises(VoicevoxApiError, match="スタイルがありません"):
        resolve_speaker_id("ずんだもん", speakers, aliases={})


def test_resolve_speaker_id_missing_style_id_raises_voicevox_api_error() -> None:
    speakers = [{"name": "ずんだもん", "styles": [{"name": "ノーマル"}]}]

    with pytest.raises(VoicevoxApiError, match="style idを取得できません"):
        resolve_speaker_id("ずんだもん", speakers, aliases={})


def test_create_audio_query_posts_to_audio_query_and_returns_json(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[Request] = []

    def fake_urlopen(request: Request, timeout: int) -> _FakeHttpResponse:
        requests.append(request)
        assert timeout == 10
        return _FakeHttpResponse(b'{"speedScale": 1.0}')

    monkeypatch.setattr(make_voicevox_assets.urllib.request, "urlopen", fake_urlopen)

    audio_query = create_audio_query("http://127.0.0.1:50021", "こんにちは", 3)

    assert audio_query == {"speedScale": 1.0}
    assert len(requests) == 1
    request = requests[0]
    parsed_url = urlparse(request.full_url)
    query = parse_qs(parsed_url.query)
    assert request.get_method() == "POST"
    assert f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}" == "http://127.0.0.1:50021/audio_query"
    assert query == {"text": ["こんにちは"], "speaker": ["3"]}


def test_create_audio_query_connection_failure_raises_voicevox_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Request, timeout: int) -> _FakeHttpResponse:
        raise URLError("connection refused")

    monkeypatch.setattr(make_voicevox_assets.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(VoicevoxApiError, match="VOICEVOXに接続できません"):
        create_audio_query("http://127.0.0.1:50021", "こんにちは", 3)


def test_create_audio_query_http_error_raises_voicevox_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Request, timeout: int) -> _FakeHttpResponse:
        raise HTTPError(request.full_url, 500, "Internal Server Error", hdrs=None, fp=None)

    monkeypatch.setattr(make_voicevox_assets.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(VoicevoxApiError, match="HTTP 500"):
        create_audio_query("http://127.0.0.1:50021", "こんにちは", 3)


def test_create_audio_query_invalid_json_raises_voicevox_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Request, timeout: int) -> _FakeHttpResponse:
        return _FakeHttpResponse(b"not json")

    monkeypatch.setattr(make_voicevox_assets.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(VoicevoxApiError, match="JSONを解析できません"):
        create_audio_query("http://127.0.0.1:50021", "こんにちは", 3)


def test_synthesize_wav_posts_to_synthesis_with_audio_query_json(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[Request] = []
    wav_bytes = b"RIFF....WAVE"

    def fake_urlopen(request: Request, timeout: int) -> _FakeHttpResponse:
        requests.append(request)
        assert timeout == 10
        return _FakeHttpResponse(wav_bytes)

    monkeypatch.setattr(make_voicevox_assets.urllib.request, "urlopen", fake_urlopen)

    result = synthesize_wav("http://127.0.0.1:50021", {"speedScale": 1.0}, 3)

    assert result == wav_bytes
    assert len(requests) == 1
    request = requests[0]
    parsed_url = urlparse(request.full_url)
    query = parse_qs(parsed_url.query)
    assert request.get_method() == "POST"
    assert f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}" == "http://127.0.0.1:50021/synthesis"
    assert query == {"speaker": ["3"]}
    assert request.data == b'{"speedScale": 1.0}'


def test_synthesize_wav_connection_failure_raises_voicevox_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Request, timeout: int) -> _FakeHttpResponse:
        raise URLError("connection refused")

    monkeypatch.setattr(make_voicevox_assets.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(VoicevoxApiError, match="VOICEVOXに接続できません"):
        synthesize_wav("http://127.0.0.1:50021", {"speedScale": 1.0}, 3)


def test_synthesize_wav_http_error_raises_voicevox_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Request, timeout: int) -> _FakeHttpResponse:
        raise HTTPError(request.full_url, 500, "Internal Server Error", hdrs=None, fp=None)

    monkeypatch.setattr(make_voicevox_assets.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(VoicevoxApiError, match="HTTP 500"):
        synthesize_wav("http://127.0.0.1:50021", {"speedScale": 1.0}, 3)


def test_synthesize_wav_empty_response_raises_voicevox_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Request, timeout: int) -> _FakeHttpResponse:
        return _FakeHttpResponse(b"")

    monkeypatch.setattr(make_voicevox_assets.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(VoicevoxApiError, match="レスポンスが空です"):
        synthesize_wav("http://127.0.0.1:50021", {"speedScale": 1.0}, 3)


def test_write_wav_bytes_writes_bytes_to_path(tmp_path: Path) -> None:
    wav_path = tmp_path / "voice.wav"

    write_wav_bytes(wav_path, b"RIFF....WAVE")

    assert wav_path.read_bytes() == b"RIFF....WAVE"


def test_write_wav_bytes_creates_parent_directories(tmp_path: Path) -> None:
    wav_path = tmp_path / "nested" / "voice.wav"

    write_wav_bytes(wav_path, b"RIFF....WAVE")

    assert wav_path.read_bytes() == b"RIFF....WAVE"


def test_write_wav_bytes_write_failure_includes_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    wav_path = tmp_path / "voice.wav"

    def fake_write_bytes(self: Path, data: bytes) -> int:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_bytes", fake_write_bytes)

    with pytest.raises(OSError) as exc_info:
        write_wav_bytes(wav_path, b"RIFF....WAVE")

    assert str(wav_path) in str(exc_info.value)


def test_synthesize_dialogue_wav_uses_voice_text_and_sets_wav_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    event = DialogueEvent(
        line_no=1,
        speaker="metan",
        voice_text="voice text",
        subtitle_text="subtitle text",
        params={},
    )
    output_path = tmp_path / "dialogue.wav"
    calls: list[tuple] = []

    def fake_create_audio_query(base_url: str, text: str, speaker_id: int) -> dict:
        calls.append(("create_audio_query", base_url, text, speaker_id))
        return {"speedScale": 1.0}

    def fake_synthesize_wav(base_url: str, audio_query: dict, speaker_id: int) -> bytes:
        calls.append(("synthesize_wav", base_url, audio_query, speaker_id))
        return b"RIFF....WAVE"

    def fake_write_wav_bytes(path: Path, wav_bytes: bytes) -> None:
        calls.append(("write_wav_bytes", path, wav_bytes))

    def fake_read_wav_info(path: Path) -> WavInfo:
        calls.append(("read_wav_info", path))
        return WavInfo(channels=1, sample_width=2, frame_rate=24000, frame_count=36000, duration_sec=1.5)

    monkeypatch.setattr(make_voicevox_assets, "create_audio_query", fake_create_audio_query)
    monkeypatch.setattr(make_voicevox_assets, "synthesize_wav", fake_synthesize_wav)
    monkeypatch.setattr(make_voicevox_assets, "write_wav_bytes", fake_write_wav_bytes)
    monkeypatch.setattr(make_voicevox_assets, "read_wav_info", fake_read_wav_info)

    result = synthesize_dialogue_wav(event, 2, "http://127.0.0.1:50021", output_path)

    assert result is event
    assert event.wav_path == output_path
    assert event.duration_sec == 1.5
    assert calls == [
        ("create_audio_query", "http://127.0.0.1:50021", "voice text", 2),
        ("synthesize_wav", "http://127.0.0.1:50021", {"speedScale": 1.0}, 2),
        ("write_wav_bytes", output_path, b"RIFF....WAVE"),
        ("read_wav_info", output_path),
    ]


def test_synthesize_dialogue_wav_create_audio_query_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    event = DialogueEvent(1, "metan", "voice text", "subtitle text", {})

    def fake_create_audio_query(base_url: str, text: str, speaker_id: int) -> dict:
        raise VoicevoxApiError("audio query failed")

    monkeypatch.setattr(make_voicevox_assets, "create_audio_query", fake_create_audio_query)

    with pytest.raises(VoicevoxApiError, match="audio query failed"):
        synthesize_dialogue_wav(event, 2, "http://127.0.0.1:50021", tmp_path / "dialogue.wav")


def test_synthesize_dialogue_wav_synthesize_wav_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    event = DialogueEvent(1, "metan", "voice text", "subtitle text", {})

    def fake_synthesize_wav(base_url: str, audio_query: dict, speaker_id: int) -> bytes:
        raise VoicevoxApiError("synthesis failed")

    monkeypatch.setattr(make_voicevox_assets, "create_audio_query", lambda base_url, text, speaker_id: {})
    monkeypatch.setattr(make_voicevox_assets, "synthesize_wav", fake_synthesize_wav)

    with pytest.raises(VoicevoxApiError, match="synthesis failed"):
        synthesize_dialogue_wav(event, 2, "http://127.0.0.1:50021", tmp_path / "dialogue.wav")


def test_synthesize_dialogue_wav_write_wav_bytes_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    event = DialogueEvent(1, "metan", "voice text", "subtitle text", {})

    def fake_write_wav_bytes(path: Path, wav_bytes: bytes) -> None:
        raise OSError("write failed")

    monkeypatch.setattr(make_voicevox_assets, "create_audio_query", lambda base_url, text, speaker_id: {})
    monkeypatch.setattr(make_voicevox_assets, "synthesize_wav", lambda base_url, audio_query, speaker_id: b"wav")
    monkeypatch.setattr(make_voicevox_assets, "write_wav_bytes", fake_write_wav_bytes)

    with pytest.raises(OSError, match="write failed"):
        synthesize_dialogue_wav(event, 2, "http://127.0.0.1:50021", tmp_path / "dialogue.wav")


def test_synthesize_dialogue_wav_read_wav_info_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    event = DialogueEvent(1, "metan", "voice text", "subtitle text", {})

    def fake_read_wav_info(path: Path) -> WavInfo:
        raise ValueError("read failed")

    monkeypatch.setattr(make_voicevox_assets, "create_audio_query", lambda base_url, text, speaker_id: {})
    monkeypatch.setattr(make_voicevox_assets, "synthesize_wav", lambda base_url, audio_query, speaker_id: b"wav")
    monkeypatch.setattr(make_voicevox_assets, "write_wav_bytes", lambda path, wav_bytes: None)
    monkeypatch.setattr(make_voicevox_assets, "read_wav_info", fake_read_wav_info)

    with pytest.raises(ValueError, match="read failed"):
        synthesize_dialogue_wav(event, 2, "http://127.0.0.1:50021", tmp_path / "dialogue.wav")


def test_synthesize_dialogue_wavs_synthesizes_dialogues_and_preserves_other_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = DialogueEvent(1, "metan", "first voice", "first subtitle", {})
    silence = SilenceEvent(line_no=2, duration_sec=0.5, source="script")
    sound_effect = SoundEffectEvent(line_no=3, path=Path("se.wav"), params={})
    second = DialogueEvent(4, "zundamon", "second voice", "second subtitle", {})
    events: list[ScriptEvent] = [first, silence, sound_effect, second]
    speakers = [{"name": "dummy"}]
    aliases = {"metan": "四国めたん"}
    calls: list[tuple] = []

    def fake_resolve_speaker_id(speaker_name: str, speakers_arg: list[dict], aliases_arg: dict[str, str]) -> int:
        calls.append(("resolve_speaker_id", speaker_name, speakers_arg, aliases_arg))
        return {"metan": 2, "zundamon": 3}[speaker_name]

    def fake_synthesize_dialogue_wav(
        event: DialogueEvent,
        speaker_id: int,
        base_url: str,
        output_path: Path,
    ) -> DialogueEvent:
        calls.append(("synthesize_dialogue_wav", event, speaker_id, base_url, output_path))
        event.wav_path = output_path
        event.duration_sec = float(speaker_id)
        return event

    monkeypatch.setattr(make_voicevox_assets, "resolve_speaker_id", fake_resolve_speaker_id)
    monkeypatch.setattr(make_voicevox_assets, "synthesize_dialogue_wav", fake_synthesize_dialogue_wav)

    out_dir = tmp_path / "wav"
    result = synthesize_dialogue_wavs(events, speakers, "http://127.0.0.1:50021", out_dir, aliases)

    assert out_dir.is_dir()
    assert result == [first, silence, sound_effect, second]
    assert result[1] is silence
    assert result[2] is sound_effect
    assert first.wav_path == out_dir / "001_metan_first_voice.wav"
    assert first.duration_sec == 2.0
    assert second.wav_path == out_dir / "002_zundamon_second_voice.wav"
    assert second.duration_sec == 3.0
    assert calls == [
        ("resolve_speaker_id", "metan", speakers, aliases),
        ("synthesize_dialogue_wav", first, 2, "http://127.0.0.1:50021", out_dir / "001_metan_first_voice.wav"),
        ("resolve_speaker_id", "zundamon", speakers, aliases),
        ("synthesize_dialogue_wav", second, 3, "http://127.0.0.1:50021", out_dir / "002_zundamon_second_voice.wav"),
    ]


def test_synthesize_dialogue_wavs_sanitizes_output_filenames(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    event = DialogueEvent(1, 'me:ta/n', 'hello? / test* voice', "subtitle", {})
    output_paths: list[Path] = []

    monkeypatch.setattr(make_voicevox_assets, "resolve_speaker_id", lambda speaker_name, speakers, aliases: 2)

    def fake_synthesize_dialogue_wav(
        event: DialogueEvent,
        speaker_id: int,
        base_url: str,
        output_path: Path,
    ) -> DialogueEvent:
        output_paths.append(output_path)
        return event

    monkeypatch.setattr(make_voicevox_assets, "synthesize_dialogue_wav", fake_synthesize_dialogue_wav)

    synthesize_dialogue_wavs([event], [], "http://127.0.0.1:50021", tmp_path, {})

    assert output_paths == [tmp_path / "001_me_ta_n_hello_test_voice.wav"]


def test_synthesize_dialogue_wavs_resolve_speaker_id_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    event = DialogueEvent(1, "metan", "voice text", "subtitle text", {})

    def fake_resolve_speaker_id(speaker_name: str, speakers: list[dict], aliases: dict[str, str]) -> int:
        raise VoicevoxApiError("speaker failed")

    monkeypatch.setattr(make_voicevox_assets, "resolve_speaker_id", fake_resolve_speaker_id)

    with pytest.raises(VoicevoxApiError, match="speaker failed"):
        synthesize_dialogue_wavs([event], [], "http://127.0.0.1:50021", tmp_path, {})


def test_synthesize_dialogue_wavs_synthesize_dialogue_wav_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    event = DialogueEvent(1, "metan", "voice text", "subtitle text", {})

    def fake_synthesize_dialogue_wav(
        event: DialogueEvent,
        speaker_id: int,
        base_url: str,
        output_path: Path,
    ) -> DialogueEvent:
        raise VoicevoxApiError("dialogue synthesis failed")

    monkeypatch.setattr(make_voicevox_assets, "resolve_speaker_id", lambda speaker_name, speakers, aliases: 2)
    monkeypatch.setattr(make_voicevox_assets, "synthesize_dialogue_wav", fake_synthesize_dialogue_wav)

    with pytest.raises(VoicevoxApiError, match="dialogue synthesis failed"):
        synthesize_dialogue_wavs([event], [], "http://127.0.0.1:50021", tmp_path, {})


def test_attach_sound_effect_info_reads_wav_info_and_preserves_event_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dialogue = DialogueEvent(1, "metan", "voice text", "subtitle text", {})
    first_sound_effect = SoundEffectEvent(2, Path("se/open.wav"), {})
    silence = SilenceEvent(line_no=3, duration_sec=0.5, source="script")
    second_sound_effect = SoundEffectEvent(4, Path("se/close.wav"), {})
    events: list[ScriptEvent] = [dialogue, first_sound_effect, silence, second_sound_effect]
    calls: list[Path] = []

    def fake_read_wav_info(path: Path) -> WavInfo:
        calls.append(path)
        duration_sec = {
            Path("se/open.wav"): 0.25,
            Path("se/close.wav"): 0.75,
        }[path]
        return WavInfo(channels=2, sample_width=2, frame_rate=44100, frame_count=1, duration_sec=duration_sec)

    monkeypatch.setattr(make_voicevox_assets, "read_wav_info", fake_read_wav_info)

    result = attach_sound_effect_info(events)

    assert result == [dialogue, first_sound_effect, silence, second_sound_effect]
    assert result[0] is dialogue
    assert result[1] is first_sound_effect
    assert result[2] is silence
    assert result[3] is second_sound_effect
    assert calls == [Path("se/open.wav"), Path("se/close.wav")]
    assert first_sound_effect.duration_sec == 0.25
    assert second_sound_effect.duration_sec == 0.75
    assert dialogue.duration_sec is None
    assert silence.duration_sec == 0.5


def test_attach_sound_effect_info_read_wav_info_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sound_effect = SoundEffectEvent(1, Path("missing.wav"), {})

    def fake_read_wav_info(path: Path) -> WavInfo:
        raise FileNotFoundError("missing wav")

    monkeypatch.setattr(make_voicevox_assets, "read_wav_info", fake_read_wav_info)

    with pytest.raises(FileNotFoundError, match="missing wav"):
        attach_sound_effect_info([sound_effect])


def test_concatenate_wavs_concatenates_events_in_order_and_returns_wav_info(tmp_path: Path) -> None:
    first_dialogue_path = tmp_path / "dialogue1.wav"
    sound_effect_path = tmp_path / "se.wav"
    second_dialogue_path = tmp_path / "dialogue2.wav"
    _write_test_wav(
        first_dialogue_path,
        channels=1,
        sample_width=2,
        frame_rate=10,
        frame_count=2,
        frames=b"\x01\x00" * 2,
    )
    _write_test_wav(
        sound_effect_path,
        channels=1,
        sample_width=2,
        frame_rate=10,
        frame_count=1,
        frames=b"\x02\x00",
    )
    _write_test_wav(
        second_dialogue_path,
        channels=1,
        sample_width=2,
        frame_rate=10,
        frame_count=1,
        frames=b"\x03\x00",
    )
    first_dialogue = DialogueEvent(1, "metan", "first", "first", {}, wav_path=first_dialogue_path)
    silence = SilenceEvent(line_no=2, duration_sec=0.2, source="script")
    sound_effect = SoundEffectEvent(3, sound_effect_path, {})
    second_dialogue = DialogueEvent(4, "zundamon", "second", "second", {}, wav_path=second_dialogue_path)
    events: list[ScriptEvent] = [first_dialogue, silence, sound_effect, second_dialogue]
    output_path = tmp_path / "nested" / "all.wav"

    info = concatenate_wavs(events, output_path)

    assert output_path.is_file()
    assert info == WavInfo(channels=1, sample_width=2, frame_rate=10, frame_count=6, duration_sec=0.6)
    assert events == [first_dialogue, silence, sound_effect, second_dialogue]
    with wave.open(str(output_path), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 10
        assert wav_file.readframes(wav_file.getnframes()) == (
            b"\x01\x00" * 2
            + b"\x00\x00" * 2
            + b"\x02\x00"
            + b"\x03\x00"
        )


def test_concatenate_wavs_mismatched_wav_format_raises_value_error(tmp_path: Path) -> None:
    first_path = tmp_path / "first.wav"
    second_path = tmp_path / "second.wav"
    _write_test_wav(first_path, channels=1, sample_width=2, frame_rate=8000, frame_count=1)
    _write_test_wav(second_path, channels=1, sample_width=2, frame_rate=16000, frame_count=1)
    events: list[ScriptEvent] = [
        DialogueEvent(1, "metan", "first", "first", {}, wav_path=first_path),
        DialogueEvent(2, "metan", "second", "second", {}, wav_path=second_path),
    ]

    with pytest.raises(ValueError, match="WAV形式が一致しません"):
        concatenate_wavs(events, tmp_path / "all.wav")


def test_concatenate_wavs_unset_dialogue_wav_path_raises_value_error(tmp_path: Path) -> None:
    events: list[ScriptEvent] = [DialogueEvent(1, "metan", "voice", "subtitle", {})]

    with pytest.raises(ValueError, match="wav_path"):
        concatenate_wavs(events, tmp_path / "all.wav")


def test_concatenate_wavs_without_audio_wav_raises_value_error(tmp_path: Path) -> None:
    events: list[ScriptEvent] = [SilenceEvent(line_no=1, duration_sec=0.5, source="script")]

    with pytest.raises(ValueError, match="音声WAVがありません"):
        concatenate_wavs(events, tmp_path / "all.wav")


def test_build_srt_cues_builds_dialogue_cues_from_accumulated_durations() -> None:
    first = DialogueEvent(
        line_no=1,
        speaker="metan",
        voice_text="voice 1",
        subtitle_text="subtitle 1",
        params={},
        duration_sec=1.2,
    )
    silence = SilenceEvent(line_no=2, duration_sec=0.3, source="script")
    sound_effect = SoundEffectEvent(line_no=3, path=Path("se.wav"), params={}, duration_sec=0.5)
    second = DialogueEvent(
        line_no=4,
        speaker="zundamon",
        voice_text="voice 2",
        subtitle_text="subtitle 2",
        params={},
        duration_sec=0.7,
    )
    events: list[ScriptEvent] = [first, silence, sound_effect, second]

    cues = build_srt_cues(events)

    assert cues == [
        SrtCue(index=1, start_sec=0.0, end_sec=1.2, text="subtitle 1"),
        SrtCue(index=2, start_sec=2.0, end_sec=2.7, text="subtitle 2"),
    ]
    assert events == [first, silence, sound_effect, second]


def test_build_srt_cues_unset_dialogue_duration_raises_value_error() -> None:
    events: list[ScriptEvent] = [DialogueEvent(1, "metan", "voice", "subtitle", {})]

    with pytest.raises(ValueError, match="DialogueEvent.duration_sec"):
        build_srt_cues(events)


def test_build_srt_cues_unset_sound_effect_duration_raises_value_error() -> None:
    events: list[ScriptEvent] = [
        DialogueEvent(1, "metan", "voice", "subtitle", {}, duration_sec=1.0),
        SoundEffectEvent(2, Path("se.wav"), {}),
    ]

    with pytest.raises(ValueError, match="SoundEffectEvent.duration_sec"):
        build_srt_cues(events)


def test_build_srt_cues_empty_subtitle_text_raises_value_error() -> None:
    events: list[ScriptEvent] = [DialogueEvent(1, "metan", "voice", "", {}, duration_sec=1.0)]

    with pytest.raises(ValueError, match="subtitle_text"):
        build_srt_cues(events)
