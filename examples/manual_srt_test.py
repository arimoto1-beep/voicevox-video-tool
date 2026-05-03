from __future__ import annotations

from pathlib import Path

from make_voicevox_assets import SrtCue, write_srt_file


def main() -> None:
    tmp_dir = Path("tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    output_path = tmp_dir / "manual_output.srt"
    cues = [
        SrtCue(index=1, start_sec=0.0, end_sec=1.5, text="こんにちは"),
        SrtCue(index=2, start_sec=2.0, end_sec=3.0, text="次の字幕"),
    ]

    write_srt_file(output_path, cues)
    content = output_path.read_text(encoding="utf-8")

    print(f"output_path={output_path.as_posix()}")
    print(f"cue_count={len(cues)}")
    print("content:")
    print(content, end="")


if __name__ == "__main__":
    main()
