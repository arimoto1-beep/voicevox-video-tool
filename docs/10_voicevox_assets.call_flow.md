# 音声・字幕生成機能 呼び出し構成

## 1. エントリーポイント

現在のCLI入口は `make_voicevox_assets.py` の `main` である。

```python
if __name__ == "__main__":
    raise SystemExit(main())
```

CLIは正式な入口に近いが、まだ初期版である。alias設定ファイル、詳細ログ、dry-run、効果音加工、動画生成などは未実装。

実行例:

```powershell
python make_voicevox_assets.py --script script.txt --out_dir wav --srt output.srt --concat all.wav --gap 0.08 --base_url http://127.0.0.1:50021
```

---

## 2. CLI実行時の全体フロー

```txt
main
  ↓
parse_args
  ↓
generate_voicevox_assets
  ↓
read_script_file
  ↓
parse_script
  ↓
insert_gap_events
  ↓
fetch_voicevox_speakers
  ↓
synthesize_dialogue_wavs
  ↓
synthesize_dialogue_wav
  ↓
create_audio_query
  ↓
synthesize_wav
  ↓
write_wav_bytes
  ↓
read_wav_info
  ↓
attach_sound_effect_info
  ↓
concatenate_wavs
  ↓
build_srt_cues
  ↓
write_srt_file
```

`synthesize_dialogue_wavs` はイベント列内の `DialogueEvent` ごとに `synthesize_dialogue_wav` を呼ぶ。

`synthesize_dialogue_wav` は1セリフ分のVOICEVOX query作成、synthesis、WAV保存、WAV長取得をまとめる。

---

## 3. main / parse_args

### main

`main(argv)` はCLI入口として以下を行う。

1. `parse_args(argv)` で `ScriptOptions` を作る。
2. `generate_voicevox_assets(options)` を呼ぶ。
3. 成功時は以下を標準出力へ表示し、`0` を返す。

```txt
audio_path=...
srt_path=...
duration_sec=...
```

4. 例外時は `stderr` に `error: ...` を表示し、`1` を返す。

### parse_args

`parse_args(argv)` はCLI引数を `ScriptOptions` へ変換する。

必須:

- `--script`
- `--out_dir`
- `--srt`
- `--concat`

任意:

- `--gap`。既定値は `0.08`
- `--base_url`。既定値は `http://127.0.0.1:50021`

---

## 4. generate_voicevox_assets

`generate_voicevox_assets(options)` は一式生成の本体統合関数である。

処理順:

```python
lines = read_script_file(options.script_path)
events = parse_script(lines, options.script_path.parent)
events = insert_gap_events(events, options.default_gap)
speakers = fetch_voicevox_speakers(options.voicevox_url)
events = synthesize_dialogue_wavs(
    events,
    speakers,
    options.voicevox_url,
    options.out_dir,
    aliases,
)
events = attach_sound_effect_info(events)
wav_info = concatenate_wavs(events, options.concat_path)
cues = build_srt_cues(events)
write_srt_file(options.srt_path, cues)
return wav_info
```

aliasは初期実装では以下を使う。

```python
{"めたん": "四国めたん", "ずんだもん": "ずんだもん"}
```

`generate_voicevox_assets` は各工程の例外を握りつぶさない。CLI層の `main` が捕捉して `error: ...` と表示する。

---

## 5. 台本読み込みからイベント列まで

### read_script_file

台本ファイルをUTF-8で読み、行リストを返す。

この時点では、空行やコメント行も文字列として残る。

### parse_script

行リストをイベント列へ変換する。

生成されるイベント:

- `DialogueEvent`
- `SilenceEvent(source="script")`
- `SoundEffectEvent`

無視される行:

- 空行
- `#` で始まるコメント行

### insert_gap_events

連続する `DialogueEvent` 同士の間に `SilenceEvent(source="gap")` を挿入する。

この工程以降、通常gapはイベント列の一部として扱う。

---

## 6. VOICEVOX音声生成

### fetch_voicevox_speakers

VOICEVOX ENGINEの `/speakers` から話者一覧を取得する。

### synthesize_dialogue_wavs

イベント列を順番に見て、`DialogueEvent` だけを処理する。

各セリフについて:

1. `resolve_speaker_id` で話者名からstyle idを得る。
2. 出力ファイル名を作る。
3. `synthesize_dialogue_wav` を呼ぶ。

`SilenceEvent` と `SoundEffectEvent` はそのまま残す。

### synthesize_dialogue_wav

1セリフ分のWAV生成を行う。

```txt
create_audio_query
  ↓
synthesize_wav
  ↓
write_wav_bytes
  ↓
read_wav_info
```

完了後、`DialogueEvent.wav_path` と `DialogueEvent.duration_sec` が設定される。

---

## 7. 効果音情報取得

### attach_sound_effect_info

`SoundEffectEvent` の `path` を `read_wav_info` に渡し、`duration_sec` を設定する。

効果音なしの台本では、実質的にイベント列をそのまま返す。

現時点では、`volume`、`fade_in`、`fade_out` は音声へ反映しない。

---

## 8. WAV連結

### concatenate_wavs

イベント列を順番に処理して、全体WAVを作る。

- `DialogueEvent`: `wav_path` のWAVを連結
- `SilenceEvent`: `duration_sec` 分の無音を生成して連結
- `SoundEffectEvent`: `path` のWAVを連結

最初に登場した音声WAVの形式を基準にする。

以下が一致しないWAVは `ValueError` になる。

- チャンネル数
- サンプル幅
- サンプリング周波数

戻り値は出力WAVの `WavInfo`。

---

## 9. SRT生成

### build_srt_cues

`current_sec` を `0.0` から積み上げる。

- `DialogueEvent`: `SrtCue` を作る
- `SilenceEvent`: 時刻だけ進める
- `SoundEffectEvent`: 時刻だけ進める

字幕本文には `DialogueEvent.subtitle_text` を使う。

### write_srt_file

`SrtCue` のリストをSRT形式に整形し、UTF-8で書き出す。

内部では以下を使う。

- `format_srt`
- `format_srt_timestamp`

---

## 10. pytestでの扱い

pytestでは本物のVOICEVOX ENGINEへ接続しない。

HTTPやファイル依存がある箇所は、以下のように差し替えて確認する。

- `urllib.request.urlopen` をmonkeypatchする
- `create_audio_query` / `synthesize_wav` / `write_wav_bytes` / `read_wav_info` をmonkeypatchする
- `resolve_speaker_id` / `synthesize_dialogue_wav` をmonkeypatchする
- `generate_voicevox_assets` のテストでは各工程の関数をmonkeypatchする
- CLIのテストでは `generate_voicevox_assets` をmonkeypatchする

WAV連結のテストでは、外部ファイルに依存せず、`tmp_path` と `wave` で小さいWAVを作る。

---

## 11. examples/manual_* の位置づけ

`examples/manual_*` は手動確認用である。

- `manual_voicevox_test.py`: VOICEVOX実接続で1セリフWAV生成を確認する。
- `manual_concatenate_test.py`: 小さいWAVを作り、WAV連結を確認する。
- `manual_srt_test.py`: `SrtCue` からSRT書き出しを確認する。
- `manual_full_pipeline_test.py`: VOICEVOX実接続で短い台本からセリフWAV、全体WAV、SRTを生成する。

これらは単体テストではなく、記事用・動作確認用のスクリプトである。

---

## 12. 初期CLIの制約

CLIは一式生成の入口として動作するが、まだ初期版である。

現時点で未対応:

- aliases設定ファイル
- aliasesのCLI引数化
- dry-run
- 詳細ログ
- 効果音の音量調整
- `fade_in` / `fade_out`
- `speed` / `pause` のVOICEVOX query反映
- 動画生成
