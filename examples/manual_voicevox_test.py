from __future__ import annotations

from pathlib import Path

from make_voicevox_assets import (
    create_audio_query,
    fetch_voicevox_speakers,
    read_wav_info,
    resolve_speaker_id,
    synthesize_wav,
    write_wav_bytes,
)


def main() -> None:
    base_url = "http://127.0.0.1:50021"
    speaker_name = "めたん"
    aliases = {"めたん": "四国めたん"}
    text = "こんにちは。テストです。"
    output_path = Path("tmp/manual_voicevox_test.wav")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    speakers = fetch_voicevox_speakers(base_url)
    speaker_id = resolve_speaker_id(speaker_name, speakers, aliases)
    audio_query = create_audio_query(base_url, text, speaker_id)
    wav_bytes = synthesize_wav(base_url, audio_query, speaker_id)
    write_wav_bytes(output_path, wav_bytes)
    wav_info = read_wav_info(output_path)

    print(f"output_path={output_path.as_posix()}")
    print(f"duration_sec={wav_info.duration_sec}")
    print(f"speaker_id={speaker_id}")


if __name__ == "__main__":
    main()
