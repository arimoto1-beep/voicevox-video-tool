from __future__ import annotations

from pathlib import Path
import wave

from make_voicevox_assets import (
    DialogueEvent,
    SilenceEvent,
    SoundEffectEvent,
    concatenate_wavs,
    read_wav_info,
)


def write_sample_wav(path: Path, *, frame_rate: int, sample_value: int, frame_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample = sample_value.to_bytes(2, byteorder="little", signed=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(frame_rate)
        wav_file.writeframes(sample * frame_count)


def main() -> None:
    tmp_dir = Path("tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    frame_rate = 8000
    dialogue_path = tmp_dir / "manual_dialogue.wav"
    se_path = tmp_dir / "manual_se.wav"
    output_path = tmp_dir / "manual_all.wav"

    write_sample_wav(dialogue_path, frame_rate=frame_rate, sample_value=1200, frame_count=1600)
    write_sample_wav(se_path, frame_rate=frame_rate, sample_value=-1200, frame_count=800)

    dialogue_info = read_wav_info(dialogue_path)
    se_info = read_wav_info(se_path)

    events = [
        DialogueEvent(
            line_no=1,
            speaker="manual",
            voice_text="manual dialogue",
            subtitle_text="manual dialogue",
            params={},
            wav_path=dialogue_path,
            duration_sec=dialogue_info.duration_sec,
        ),
        SilenceEvent(line_no=2, duration_sec=0.1, source="manual"),
        SoundEffectEvent(line_no=3, path=se_path, params={}, duration_sec=se_info.duration_sec),
    ]

    wav_info = concatenate_wavs(events, output_path)

    print(f"output_path={output_path.as_posix()}")
    print(f"duration_sec={wav_info.duration_sec}")
    print(f"channels={wav_info.channels}")
    print(f"sample_width={wav_info.sample_width}")
    print(f"frame_rate={wav_info.frame_rate}")


if __name__ == "__main__":
    main()
