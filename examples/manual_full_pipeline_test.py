from __future__ import annotations

from pathlib import Path

from make_voicevox_assets import (
    DialogueEvent,
    attach_sound_effect_info,
    build_srt_cues,
    concatenate_wavs,
    fetch_voicevox_speakers,
    insert_gap_events,
    parse_script,
    read_script_file,
    synthesize_dialogue_wavs,
    write_srt_file,
)


def main() -> None:
    script_path = Path("tmp/full_pipeline/script.txt")
    out_dir = Path("tmp/full_pipeline")
    wav_dir = Path("tmp/full_pipeline/wav")
    concat_path = Path("tmp/full_pipeline/all.wav")
    srt_path = Path("tmp/full_pipeline/output.srt")
    base_url = "http://127.0.0.1:50021"
    aliases = {"めたん": "四国めたん", "ずんだもん": "ずんだもん"}
    default_gap = 0.3

    script_text = """\
めたん：こんにちは。テストです。
ずんだもん：音声と字幕をまとめて作るのだ。
"""

    out_dir.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script_text, encoding="utf-8")

    lines = read_script_file(script_path)
    events = parse_script(lines, script_path.parent)
    events = insert_gap_events(events, default_gap)
    speakers = fetch_voicevox_speakers(base_url)
    events = synthesize_dialogue_wavs(events, speakers, base_url, wav_dir, aliases)
    events = attach_sound_effect_info(events)
    wav_info = concatenate_wavs(events, concat_path)
    cues = build_srt_cues(events)
    write_srt_file(srt_path, cues)

    dialogue_count = sum(isinstance(event, DialogueEvent) for event in events)

    print(f"script_path={script_path.as_posix()}")
    print(f"wav_dir={wav_dir.as_posix()}")
    print(f"audio_path={concat_path.as_posix()}")
    print(f"srt_path={srt_path.as_posix()}")
    print(f"duration_sec={wav_info.duration_sec}")
    print(f"cue_count={len(cues)}")
    print(f"dialogue_count={dialogue_count}")


if __name__ == "__main__":
    main()
