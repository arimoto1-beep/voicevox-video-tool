from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TypeAlias
import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import wave


DIALOGUE_PARAM_KEYS = {"speed", "pause"}
SOUND_EFFECT_PARAM_KEYS = {"volume", "fade_in", "fade_out"}
DEFAULT_SPEAKER_ALIASES = {"めたん": "四国めたん", "ずんだもん": "ずんだもん"}


class ScriptParseError(ValueError):
    """Raised when a script line cannot be parsed."""


class VoicevoxApiError(RuntimeError):
    """Raised when the VOICEVOX API cannot return usable data."""


@dataclass
class ScriptOptions:
    script_path: Path
    out_dir: Path
    srt_path: Path
    concat_path: Path
    voicevox_url: str = "http://127.0.0.1:50021"
    default_gap: float = 0.0
    default_speed: float = 1.0
    default_pause: float | None = None
    speaker_aliases: dict[str, str] = field(default_factory=dict)
    split_long_dialogue: bool = False
    dialogue_split_chars: int = 18
    dialogue_split_min_chars: int = 6


@dataclass
class DialogueEvent:
    line_no: int
    speaker: str
    voice_text: str
    subtitle_text: str
    params: dict[str, str]
    wav_path: Path | None = None
    duration_sec: float | None = None


@dataclass
class SilenceEvent:
    line_no: int | None
    duration_sec: float
    source: str


@dataclass
class SoundEffectEvent:
    line_no: int
    path: Path
    params: dict[str, str]
    duration_sec: float | None = None


@dataclass
class WavInfo:
    channels: int
    sample_width: int
    frame_rate: int
    frame_count: int
    duration_sec: float


@dataclass
class SrtCue:
    index: int
    start_sec: float
    end_sec: float
    text: str


ScriptEvent: TypeAlias = DialogueEvent | SilenceEvent | SoundEffectEvent


def read_script_file(script_path: Path) -> list[str]:
    """Read a UTF-8 script file and return lines without newline characters."""
    if not script_path.exists():
        raise FileNotFoundError(f"台本ファイルが見つかりません: {script_path}")
    if not script_path.is_file():
        raise OSError(f"台本ファイルではありません: {script_path}")

    try:
        return script_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise OSError(f"台本ファイルを読み込めません: {script_path}") from exc


def parse_script(lines: list[str], script_dir: Path) -> list[ScriptEvent]:
    """Parse script lines into dialogue, silence, and sound-effect events."""
    events: list[ScriptEvent] = []
    previous_speaker: str | None = None

    for index, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        silence_event = _parse_silence_line(line, index)
        if silence_event is not None:
            events.append(silence_event)
            continue

        sound_effect_event = _parse_sound_effect_line(line, index, script_dir)
        if sound_effect_event is not None:
            events.append(sound_effect_event)
            continue

        dialogue_event = _parse_dialogue_line(line, index, previous_speaker)
        previous_speaker = dialogue_event.speaker
        events.append(dialogue_event)

    return events


def insert_gap_events(events: list[ScriptEvent], gap_sec: float) -> list[ScriptEvent]:
    """Insert normal dialogue gaps as SilenceEvent(source="gap")."""
    if gap_sec < 0:
        raise ValueError(f"gap_sec は0以上で指定してください: {gap_sec}")
    if gap_sec == 0:
        return events

    result: list[ScriptEvent] = []
    for current, next_event in zip(events, events[1:]):
        result.append(current)
        # 初期実装では、通常gapは連続するセリフ同士の間だけに入れる。
        # SEや明示的な間の前後にも入れると、台本で指定したタイミングと二重になりやすいため。
        if isinstance(current, DialogueEvent) and isinstance(next_event, DialogueEvent):
            result.append(SilenceEvent(line_no=None, duration_sec=gap_sec, source="gap"))

    if events:
        result.append(events[-1])

    return result


def split_long_dialogue_event(
    event: DialogueEvent,
    max_chars: int,
    min_chars: int,
) -> list[DialogueEvent]:
    """Split one long dialogue before synthesis while preserving dialogue metadata."""
    if max_chars <= 0:
        raise ValueError(f"max_chars は1以上で指定してください: {max_chars}")
    if min_chars < 0:
        raise ValueError(f"min_chars は0以上で指定してください: {min_chars}")
    if min_chars > max_chars:
        raise ValueError(f"min_chars は max_chars 以下で指定してください: {min_chars}")

    if event.voice_text != event.subtitle_text:
        return [event]

    parts = split_text_by_rules(event.voice_text, max_chars=max_chars, min_chars=min_chars)
    if len(parts) <= 1:
        return [event]

    return [
        replace(
            event,
            voice_text=part,
            subtitle_text=part,
            params=event.params.copy(),
            wav_path=None,
            duration_sec=None,
        )
        for part in parts
    ]


def split_long_dialogue_events(
    events: list[ScriptEvent],
    max_chars: int,
    min_chars: int,
) -> list[ScriptEvent]:
    """Apply long dialogue splitting to a whole script event list."""
    if max_chars <= 0:
        raise ValueError(f"max_chars 縺ｯ1莉･荳翫〒謖・ｮ壹＠縺ｦ縺上□縺輔＞: {max_chars}")
    if min_chars < 0:
        raise ValueError(f"min_chars 縺ｯ0莉･荳翫〒謖・ｮ壹＠縺ｦ縺上□縺輔＞: {min_chars}")
    if min_chars > max_chars:
        raise ValueError(f"min_chars 縺ｯ max_chars 莉･荳九〒謖・ｮ壹＠縺ｦ縺上□縺輔＞: {min_chars}")

    result: list[ScriptEvent] = []
    for event in events:
        if isinstance(event, DialogueEvent):
            result.extend(split_long_dialogue_event(event, max_chars=max_chars, min_chars=min_chars))
        else:
            result.append(event)
    return result


def split_text_by_rules(text: str, max_chars: int, min_chars: int) -> list[str]:
    """Split text by Japanese punctuation first, falling back to character count."""
    if max_chars <= 0:
        raise ValueError(f"max_chars は1以上で指定してください: {max_chars}")
    if min_chars < 0:
        raise ValueError(f"min_chars は0以上で指定してください: {min_chars}")
    if min_chars > max_chars:
        raise ValueError(f"min_chars は max_chars 以下で指定してください: {min_chars}")

    remaining = text.strip()
    if len(remaining) <= max_chars:
        return [remaining] if remaining else []

    parts: list[str] = []
    while len(remaining) > max_chars:
        split_index = _find_split_index(remaining, max_chars=max_chars, min_chars=min_chars)
        if split_index is None:
            split_index = max_chars

        part = remaining[:split_index].strip()
        rest = remaining[split_index:].strip()
        if not part:
            break
        if rest and len(rest) < min_chars:
            break

        parts.append(part)
        remaining = rest

    if remaining:
        parts.append(remaining)

    return parts


def read_wav_info(path: Path) -> WavInfo:
    """Read WAV format information and duration from a WAV file."""
    if not path.exists():
        raise FileNotFoundError(f"WAVファイルが見つかりません: {path}")
    if not path.is_file():
        raise OSError(f"WAVファイルではありません: {path}")

    try:
        with wave.open(str(path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frame_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"WAVファイルとして読み込めません: {path}") from exc
    except OSError as exc:
        raise OSError(f"WAVファイルを読み込めません: {path}") from exc

    if frame_rate <= 0:
        raise ValueError(f"WAVファイルのサンプリング周波数が不正です: {path}")

    return WavInfo(
        channels=channels,
        sample_width=sample_width,
        frame_rate=frame_rate,
        frame_count=frame_count,
        duration_sec=frame_count / frame_rate,
    )


def fetch_voicevox_speakers(base_url: str) -> list[dict]:
    """Fetch speaker definitions from the VOICEVOX ENGINE /speakers API."""
    speakers_url = f"{base_url.rstrip('/')}/speakers"

    try:
        with urllib.request.urlopen(speakers_url, timeout=10) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                raise VoicevoxApiError(f"VOICEVOX /speakers の取得に失敗しました: HTTP {status}")
            body = response.read()
    except VoicevoxApiError:
        raise
    except urllib.error.HTTPError as exc:
        raise VoicevoxApiError(f"VOICEVOX /speakers の取得に失敗しました: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise VoicevoxApiError(f"VOICEVOXに接続できません: {speakers_url} ({exc.reason})") from exc
    except OSError as exc:
        raise VoicevoxApiError(f"VOICEVOXに接続できません: {speakers_url}") from exc

    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VoicevoxApiError(f"VOICEVOX /speakers のJSONを解析できません: {speakers_url}") from exc

    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise VoicevoxApiError(f"VOICEVOX /speakers のJSON形式が不正です: {speakers_url}")

    return data


def resolve_speaker_id(speaker_name: str, speakers: list[dict], aliases: dict[str, str]) -> int:
    """Resolve a script speaker name to the first VOICEVOX style id."""
    resolved_name = aliases.get(speaker_name, speaker_name)

    for speaker in speakers:
        if speaker.get("name") != resolved_name:
            continue

        styles = speaker.get("styles")
        if not isinstance(styles, list) or not styles:
            raise VoicevoxApiError(f"VOICEVOX話者 '{resolved_name}' に利用可能なスタイルがありません")

        first_style = styles[0]
        if not isinstance(first_style, dict) or "id" not in first_style:
            raise VoicevoxApiError(f"VOICEVOX話者 '{resolved_name}' のstyle idを取得できません")

        style_id = first_style["id"]
        if not isinstance(style_id, int):
            raise VoicevoxApiError(f"VOICEVOX話者 '{resolved_name}' のstyle idが不正です")

        return style_id

    raise VoicevoxApiError(f"VOICEVOX話者 '{speaker_name}' が見つかりません")


def create_audio_query(base_url: str, text: str, speaker_id: int) -> dict:
    """Create a VOICEVOX audio query for one dialogue text."""
    query = urllib.parse.urlencode({"text": text, "speaker": speaker_id})
    url = f"{base_url.rstrip('/')}/audio_query?{query}"
    request = urllib.request.Request(url, data=b"", method="POST")

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                raise VoicevoxApiError(f"VOICEVOX /audio_query の作成に失敗しました: HTTP {status}")
            body = response.read()
    except VoicevoxApiError:
        raise
    except urllib.error.HTTPError as exc:
        raise VoicevoxApiError(f"VOICEVOX /audio_query の作成に失敗しました: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise VoicevoxApiError(f"VOICEVOXに接続できません: {url} ({exc.reason})") from exc
    except OSError as exc:
        raise VoicevoxApiError(f"VOICEVOXに接続できません: {url}") from exc

    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VoicevoxApiError(f"VOICEVOX /audio_query のJSONを解析できません: {url}") from exc

    if not isinstance(data, dict):
        raise VoicevoxApiError(f"VOICEVOX /audio_query のJSON形式が不正です: {url}")

    return data


def synthesize_wav(base_url: str, audio_query: dict, speaker_id: int) -> bytes:
    """Synthesize WAV bytes from a VOICEVOX audio query."""
    query = urllib.parse.urlencode({"speaker": speaker_id})
    url = f"{base_url.rstrip('/')}/synthesis?{query}"
    request = urllib.request.Request(
        url,
        data=json.dumps(audio_query).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                raise VoicevoxApiError(f"VOICEVOX /synthesis に失敗しました: HTTP {status}")
            wav_bytes = response.read()
    except VoicevoxApiError:
        raise
    except urllib.error.HTTPError as exc:
        raise VoicevoxApiError(f"VOICEVOX /synthesis に失敗しました: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise VoicevoxApiError(f"VOICEVOXに接続できません: {url} ({exc.reason})") from exc
    except OSError as exc:
        raise VoicevoxApiError(f"VOICEVOXに接続できません: {url}") from exc

    if not wav_bytes:
        raise VoicevoxApiError(f"VOICEVOX /synthesis のレスポンスが空です: {url}")

    return wav_bytes


def write_wav_bytes(path: Path, wav_bytes: bytes) -> None:
    """Write WAV bytes to a file, creating parent directories as needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(wav_bytes)
    except OSError as exc:
        raise OSError(f"WAVファイルを書き込めません: {path}") from exc


def synthesize_dialogue_wav(
    event: DialogueEvent,
    speaker_id: int,
    base_url: str,
    output_path: Path,
) -> DialogueEvent:
    """Synthesize one dialogue event and attach its WAV path and duration."""
    audio_query = create_audio_query(base_url, event.voice_text, speaker_id)
    wav_bytes = synthesize_wav(base_url, audio_query, speaker_id)
    write_wav_bytes(output_path, wav_bytes)
    wav_info = read_wav_info(output_path)

    event.wav_path = output_path
    event.duration_sec = wav_info.duration_sec
    return event


def synthesize_dialogue_wavs(
    events: list[ScriptEvent],
    speakers: list[dict],
    base_url: str,
    out_dir: Path,
    aliases: dict[str, str],
) -> list[ScriptEvent]:
    """Synthesize WAV files for dialogue events while preserving event order."""
    out_dir.mkdir(parents=True, exist_ok=True)

    result: list[ScriptEvent] = []
    dialogue_index = 0
    for event in events:
        if not isinstance(event, DialogueEvent):
            result.append(event)
            continue

        dialogue_index += 1
        speaker_id = resolve_speaker_id(event.speaker, speakers, aliases)
        output_path = out_dir / _make_dialogue_wav_filename(dialogue_index, event)
        result.append(synthesize_dialogue_wav(event, speaker_id, base_url, output_path))

    return result


def attach_sound_effect_info(events: list[ScriptEvent]) -> list[ScriptEvent]:
    """Attach WAV duration information to sound-effect events."""
    result: list[ScriptEvent] = []
    for event in events:
        if not isinstance(event, SoundEffectEvent):
            result.append(event)
            continue

        wav_info = read_wav_info(event.path)
        event.duration_sec = wav_info.duration_sec
        result.append(event)

    return result


def concatenate_wavs(events: list[ScriptEvent], output_path: Path) -> WavInfo:
    """Concatenate dialogue WAVs, sound effects, and silence into one WAV file."""
    base_format = _find_base_wav_format(events)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(output_path), "wb") as output_wav:
        output_wav.setnchannels(base_format.channels)
        output_wav.setsampwidth(base_format.sample_width)
        output_wav.setframerate(base_format.frame_rate)

        for event in events:
            if isinstance(event, DialogueEvent):
                if event.wav_path is None:
                    raise ValueError("DialogueEvent.wav_path が未設定です")
                _write_wav_file_frames(output_wav, event.wav_path, base_format)
            elif isinstance(event, SilenceEvent):
                output_wav.writeframes(_make_silence_frames(event.duration_sec, base_format))
            elif isinstance(event, SoundEffectEvent):
                _write_wav_file_frames(output_wav, event.path, base_format)

    return read_wav_info(output_path)


def build_srt_cues(events: list[ScriptEvent]) -> list[SrtCue]:
    """Build SRT cue data from dialogue events and accumulated durations."""
    cues: list[SrtCue] = []
    current_sec = 0.0

    for event in events:
        if isinstance(event, DialogueEvent):
            if event.duration_sec is None:
                raise ValueError("DialogueEvent.duration_sec が未設定です")
            if not event.subtitle_text:
                raise ValueError("DialogueEvent.subtitle_text が空です")

            start_sec = current_sec
            end_sec = current_sec + event.duration_sec
            cues.append(SrtCue(index=len(cues) + 1, start_sec=start_sec, end_sec=end_sec, text=event.subtitle_text))
            current_sec = end_sec
        elif isinstance(event, SilenceEvent):
            current_sec += event.duration_sec
        elif isinstance(event, SoundEffectEvent):
            if event.duration_sec is None:
                raise ValueError("SoundEffectEvent.duration_sec が未設定です")
            current_sec += event.duration_sec

    return cues


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds as an SRT timestamp: HH:MM:SS,mmm."""
    if seconds < 0:
        raise ValueError(f"seconds は0以上で指定してください: {seconds}")

    total_milliseconds = round(seconds * 1000)
    milliseconds = total_milliseconds % 1000
    total_seconds = total_milliseconds // 1000
    second = total_seconds % 60
    total_minutes = total_seconds // 60
    minute = total_minutes % 60
    hour = total_minutes // 60
    return f"{hour:02d}:{minute:02d}:{second:02d},{milliseconds:03d}"


def format_srt(cues: list[SrtCue]) -> str:
    """Format SRT cues as an SRT file body."""
    blocks: list[str] = []
    for cue in cues:
        if cue.end_sec < cue.start_sec:
            raise ValueError(f"SrtCue.end_sec が start_sec より小さいです: {cue}")
        if not cue.text:
            raise ValueError("SrtCue.text が空です")

        blocks.append(
            "\n".join(
                [
                    str(cue.index),
                    f"{format_srt_timestamp(cue.start_sec)} --> {format_srt_timestamp(cue.end_sec)}",
                    cue.text,
                ]
            )
        )

    if not blocks:
        return ""
    return "\n\n".join(blocks) + "\n"


def write_srt_file(path: Path, cues: list[SrtCue]) -> None:
    """Write SRT cues to a UTF-8 encoded file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_srt(cues), encoding="utf-8")


def generate_voicevox_assets(options: ScriptOptions) -> WavInfo:
    """Generate dialogue WAVs, concatenated audio, and an SRT file from a script."""
    aliases = options.speaker_aliases or DEFAULT_SPEAKER_ALIASES

    lines = read_script_file(options.script_path)
    events = parse_script(lines, options.script_path.parent)
    if options.split_long_dialogue:
        events = split_long_dialogue_events(
            events,
            max_chars=options.dialogue_split_chars,
            min_chars=options.dialogue_split_min_chars,
        )
    events = insert_gap_events(events, options.default_gap)
    speakers = fetch_voicevox_speakers(options.voicevox_url)
    events = synthesize_dialogue_wavs(events, speakers, options.voicevox_url, options.out_dir, aliases)
    events = attach_sound_effect_info(events)
    wav_info = concatenate_wavs(events, options.concat_path)
    cues = build_srt_cues(events)
    write_srt_file(options.srt_path, cues)
    return wav_info


def parse_args(argv: list[str] | None = None) -> ScriptOptions:
    parser = argparse.ArgumentParser(description="Generate VOICEVOX audio and SRT assets from a script.")
    parser.add_argument("--script", required=True, type=Path, help="Input script file path.")
    parser.add_argument("--out_dir", required=True, type=Path, help="Output directory for dialogue WAV files.")
    parser.add_argument("--srt", required=True, type=Path, help="Output SRT file path.")
    parser.add_argument("--concat", required=True, type=Path, help="Output concatenated WAV file path.")
    parser.add_argument("--gap", default=0.08, type=float, help="Gap seconds inserted between dialogues.")
    parser.add_argument(
        "--base_url",
        default="http://127.0.0.1:50021",
        help="VOICEVOX ENGINE base URL.",
    )
    parser.add_argument(
        "--split-long-dialogue",
        action="store_true",
        help="Split long dialogue events before VOICEVOX synthesis.",
    )
    parser.add_argument(
        "--dialogue-split-chars",
        default=18,
        type=int,
        help="Target character count for splitting long dialogue events.",
    )
    parser.add_argument(
        "--dialogue-split-min-chars",
        default=6,
        type=int,
        help="Minimum character count for split dialogue fragments.",
    )
    args = parser.parse_args(argv)

    return ScriptOptions(
        script_path=args.script,
        out_dir=args.out_dir,
        srt_path=args.srt,
        concat_path=args.concat,
        voicevox_url=args.base_url,
        default_gap=args.gap,
        speaker_aliases=DEFAULT_SPEAKER_ALIASES.copy(),
        split_long_dialogue=args.split_long_dialogue,
        dialogue_split_chars=args.dialogue_split_chars,
        dialogue_split_min_chars=args.dialogue_split_min_chars,
    )


def main(argv: list[str] | None = None) -> int:
    try:
        options = parse_args(argv)
        wav_info = generate_voicevox_assets(options)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"audio_path={options.concat_path.as_posix()}")
    print(f"srt_path={options.srt_path.as_posix()}")
    print(f"duration_sec={wav_info.duration_sec}")
    return 0


def _make_dialogue_wav_filename(index: int, event: DialogueEvent) -> str:
    speaker = _sanitize_filename_part(event.speaker, fallback="speaker", max_length=24)
    text = _sanitize_filename_part(event.voice_text, fallback="dialogue", max_length=32)
    return f"{index:03d}_{speaker}_{text}.wav"


def _sanitize_filename_part(value: str, *, fallback: str, max_length: int) -> str:
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value)
    safe = re.sub(r"\s+", "_", safe)
    safe = re.sub(r"_+", "_", safe).strip("._ ")
    if not safe:
        safe = fallback
    return safe[:max_length].rstrip("._ ") or fallback


def _find_split_index(text: str, *, max_chars: int, min_chars: int) -> int | None:
    for separators in ("。", "、", "！？", " 　"):
        index = _find_separator_before_limit(text, separators, max_chars=max_chars, min_chars=min_chars)
        if index is not None:
            return index

    for separators in ("。", "、", "！？", " 　"):
        index = _find_separator_after_limit(text, separators, max_chars=max_chars, min_chars=min_chars)
        if index is not None:
            return index

    return None


def _find_separator_before_limit(text: str, separators: str, *, max_chars: int, min_chars: int) -> int | None:
    for index in range(min(max_chars, len(text)) - 1, min_chars - 2, -1):
        if text[index] in separators:
            split_index = index + 1
            if _is_valid_split(text, split_index, min_chars=min_chars):
                return split_index
    return None


def _find_separator_after_limit(text: str, separators: str, *, max_chars: int, min_chars: int) -> int | None:
    search_limit = min(len(text), max_chars + min_chars)
    for index in range(max_chars, search_limit):
        if text[index] in separators:
            split_index = index + 1
            if _is_valid_split(text, split_index, min_chars=min_chars):
                return split_index
    return None


def _is_valid_split(text: str, split_index: int, *, min_chars: int) -> bool:
    left = text[:split_index].strip()
    right = text[split_index:].strip()
    if not left or not right:
        return False
    return len(left) >= min_chars and len(right) >= min_chars


def _find_base_wav_format(events: list[ScriptEvent]) -> WavInfo:
    for event in events:
        if isinstance(event, DialogueEvent):
            if event.wav_path is None:
                raise ValueError("DialogueEvent.wav_path が未設定です")
            return read_wav_info(event.wav_path)
        if isinstance(event, SoundEffectEvent):
            return read_wav_info(event.path)

    raise ValueError("連結対象の音声WAVがありません")


def _write_wav_file_frames(output_wav: wave.Wave_write, path: Path, base_format: WavInfo) -> None:
    with wave.open(str(path), "rb") as input_wav:
        channels = input_wav.getnchannels()
        sample_width = input_wav.getsampwidth()
        frame_rate = input_wav.getframerate()
        if (
            channels != base_format.channels
            or sample_width != base_format.sample_width
            or frame_rate != base_format.frame_rate
        ):
            raise ValueError(f"WAV形式が一致しません: {path}")

        output_wav.writeframes(input_wav.readframes(input_wav.getnframes()))


def _make_silence_frames(duration_sec: float, base_format: WavInfo) -> bytes:
    frame_count = round(duration_sec * base_format.frame_rate)
    bytes_per_frame = base_format.channels * base_format.sample_width
    if base_format.sample_width == 1:
        return b"\x80" * bytes_per_frame * frame_count
    return b"\x00" * bytes_per_frame * frame_count


def _parse_silence_line(line: str, line_no: int) -> SilenceEvent | None:
    match = re.fullmatch(r"\(間\s+([+-]?(?:\d+(?:\.\d*)?|\.\d+))\)", line)
    if match is None:
        if line.startswith("(間"):
            raise ScriptParseError(f"{line_no}行目: 間の形式が不正です: {line}")
        return None

    duration_sec = _parse_non_negative_float(match.group(1), line_no, "間の秒数")
    return SilenceEvent(line_no=line_no, duration_sec=duration_sec, source="script")


def _parse_sound_effect_line(
    line: str,
    line_no: int,
    script_dir: Path,
) -> SoundEffectEvent | None:
    body, params = _extract_inline_params(line, line_no)
    match = re.fullmatch(r"\(SE\s+(.+)\)", body)
    if match is None:
        if body.startswith("(SE"):
            raise ScriptParseError(f"{line_no}行目: 効果音の形式が不正です: {line}")
        return None

    _validate_params(params, SOUND_EFFECT_PARAM_KEYS, line_no)
    raw_path = match.group(1).strip()
    if not raw_path:
        raise ScriptParseError(f"{line_no}行目: 効果音ファイルのパスが空です")

    effect_path = Path(raw_path)
    if not effect_path.is_absolute():
        effect_path = script_dir / effect_path

    return SoundEffectEvent(line_no=line_no, path=effect_path, params=params)


def _parse_dialogue_line(
    line: str,
    line_no: int,
    previous_speaker: str | None,
) -> DialogueEvent:
    body, params = _extract_inline_params(line, line_no)
    _validate_params(params, DIALOGUE_PARAM_KEYS, line_no)

    speaker, text = _split_speaker_and_text(body, previous_speaker, line_no)
    voice_text, subtitle_text = _split_voice_and_subtitle_text(text, line_no)

    return DialogueEvent(
        line_no=line_no,
        speaker=speaker,
        voice_text=voice_text,
        subtitle_text=subtitle_text,
        params=params,
    )


def _extract_inline_params(text: str, line_no: int) -> tuple[str, dict[str, str]]:
    stripped = text.strip()
    if not stripped.endswith("}"):
        if "{" in stripped or "}" in stripped:
            raise ScriptParseError(f"{line_no}行目: 個別パラメータの形式が不正です: {text}")
        return stripped, {}

    start = stripped.rfind("{")
    if start == -1:
        raise ScriptParseError(f"{line_no}行目: 個別パラメータの形式が不正です: {text}")

    body = stripped[:start].rstrip()
    param_text = stripped[start + 1 : -1].strip()
    params: dict[str, str] = {}
    if not param_text:
        return body, params

    for item in param_text.split(","):
        if "=" not in item:
            raise ScriptParseError(f"{line_no}行目: 個別パラメータは key=value 形式で指定してください: {item.strip()}")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ScriptParseError(f"{line_no}行目: 個別パラメータのキーまたは値が空です: {item.strip()}")
        params[key] = value

    return body, params


def _validate_params(params: dict[str, str], allowed_keys: set[str], line_no: int) -> None:
    for key in params:
        if key not in allowed_keys:
            allowed = ", ".join(sorted(allowed_keys))
            raise ScriptParseError(f"{line_no}行目: 未対応の個別パラメータです: {key} (許可: {allowed})")


def _split_speaker_and_text(
    body: str,
    previous_speaker: str | None,
    line_no: int,
) -> tuple[str, str]:
    separator_positions = [pos for pos in (body.find("："), body.find(":")) if pos != -1]
    if separator_positions:
        pos = min(separator_positions)
        speaker = body[:pos].strip()
        text = body[pos + 1 :].strip()
        if not speaker:
            raise ScriptParseError(f"{line_no}行目: 話者名が空です")
    else:
        if previous_speaker is None:
            raise ScriptParseError(f"{line_no}行目: 話者省略セリフの前に話者が存在しません")
        speaker = previous_speaker
        text = body.strip()

    if not text:
        raise ScriptParseError(f"{line_no}行目: セリフ本文が空です")

    return speaker, text


def _split_voice_and_subtitle_text(text: str, line_no: int) -> tuple[str, str]:
    if "||" in text:
        voice_text, subtitle_text = text.split("||", 1)
        voice_text = voice_text.strip()
        subtitle_text = subtitle_text.strip()
    else:
        voice_text = text.strip()
        subtitle_text = text.strip()

    if not voice_text:
        raise ScriptParseError(f"{line_no}行目: 読み上げ用テキストが空です")
    if not subtitle_text:
        raise ScriptParseError(f"{line_no}行目: 字幕用テキストが空です")

    return voice_text, subtitle_text


def _parse_non_negative_float(value: str, line_no: int, label: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise ScriptParseError(f"{line_no}行目: {label}が数値ではありません: {value}") from exc

    if number < 0:
        raise ScriptParseError(f"{line_no}行目: {label}は0以上で指定してください: {value}")

    return number


if __name__ == "__main__":
    raise SystemExit(main())
