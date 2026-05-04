# 音声・字幕生成機能 仕様

## 1. 機能概要

台本ファイルを読み込み、VOICEVOX ENGINEを使ってセリフごとのWAVを生成する。

生成したセリフWAV、無音、効果音WAVをイベント列の順番に連結し、全体音声WAVを作成する。

また、イベント列の長さを積み上げてSRT字幕ファイルを生成する。

現時点では、`generate_voicevox_assets` とCLIから以下の成果物を生成できる。

- セリフごとのWAV
- 全体音声WAV
- SRT字幕ファイル

動画生成、字幕焼き込み、口パクなどは対象外である。

---

## 2. 入力

### 2.1 台本ファイル

UTF-8のテキストファイルを入力とする。

例:

```txt
めたん：こんにちは。テストです。
ずんだもん：音声と字幕をまとめて作るのだ。
```

台本には以下を書ける。

- 話者つきセリフ
- 話者省略セリフ
- 読み上げ文と字幕文の分離
- 間
- 効果音
- コメント
- 空行
- 個別パラメータ

### 2.2 VOICEVOX ENGINE

セリフ音声はVOICEVOX ENGINEへHTTP接続して生成する。

既定の接続先は以下。

```txt
http://127.0.0.1:50021
```

CLIでは `--base_url` で変更できる。

### 2.3 効果音WAV

効果音はWAVファイルとして指定する。

相対パスは台本ファイルのあるディレクトリを基準に解決する。

効果音WAVは全体音声に連結され、SRTの時刻計算にも反映される。ただし、字幕本文には出力しない。

---

## 3. 出力

### 3.1 セリフごとのWAV

`synthesize_dialogue_wavs` が `DialogueEvent` ごとにWAVを生成する。

出力ファイル名はセリフ単位の連番を含む。

例:

```txt
wav/001_めたん_こんにちは。テストです。.wav
wav/002_ずんだもん_音声と字幕をまとめて作るのだ。.wav
```

### 3.2 全体音声WAV

`concatenate_wavs` がイベント列を順番に連結し、全体音声WAVを作る。

CLI例では `--concat all.wav` で指定する。

### 3.3 SRT字幕ファイル

`build_srt_cues` で字幕キューを作り、`write_srt_file` でSRTファイルを書き出す。

CLI例では `--srt output.srt` で指定する。

---

## 4. 台本フォーマット

### 4.1 話者つきセリフ

全角コロンまたは半角コロンで話者名と本文を区切る。

```txt
めたん：こんにちは。
ずんだもん:了解なのだ。
```

### 4.2 話者省略

話者名を省略した行は、直前の話者を引き継ぐ。

```txt
めたん：最初のセリフ
続きのセリフ
```

直前の話者がない状態で話者省略行が出た場合は `ScriptParseError` になる。

### 4.3 voice_text / subtitle_text 分離

`||` で読み上げ用テキストと字幕用テキストを分離できる。

```txt
めたん：あーそれ || あ、それ
```

- 左側: `voice_text`
- 右側: `subtitle_text`

`||` がない場合は、読み上げ用テキストと字幕用テキストは同じになる。

### 4.4 間

```txt
(間 0.25)
```

秒数で無音を指定する。

`SilenceEvent(source="script")` として扱い、全体音声とSRT時刻計算に反映する。

### 4.5 効果音

```txt
(SE se\pop.wav)
```

`SoundEffectEvent` として扱う。

効果音WAVは全体音声に連結され、SRT時刻計算にも反映される。

### 4.6 コメントと空行

`#` で始まる行と空行は、`parse_script` で無視される。

```txt
# コメント
```

### 4.7 個別パラメータ

行末に `{key=value}` 形式で指定できる。

セリフ用:

- `speed`
- `pause`

効果音用:

- `volume`
- `fade_in`
- `fade_out`

現時点では、これらのパラメータは解析・検証されるが、音声加工やVOICEVOX queryへの反映は未実装である。

未対応のキーや不正な形式は `ScriptParseError` になる。

---

## 5. 処理の大まかな流れ

CLI実行時は `main` から `generate_voicevox_assets` を呼び、以下の順番で処理する。

1. `read_script_file`
2. `parse_script`
3. `insert_gap_events`
4. `fetch_voicevox_speakers`
5. `synthesize_dialogue_wavs`
6. `attach_sound_effect_info`
7. `concatenate_wavs`
8. `build_srt_cues`
9. `write_srt_file`

`synthesize_dialogue_wavs` の内部では、各 `DialogueEvent` について以下を呼ぶ。

1. `resolve_speaker_id`
2. `synthesize_dialogue_wav`
3. `create_audio_query`
4. `synthesize_wav`
5. `write_wav_bytes`
6. `read_wav_info`

---

## 6. CLIの使い方

```powershell
python make_voicevox_assets.py --script script.txt --out_dir wav --srt output.srt --concat all.wav --gap 0.08 --base_url http://127.0.0.1:50021
```

必須引数:

- `--script`: 台本ファイル
- `--out_dir`: セリフごとのWAV出力ディレクトリ
- `--srt`: SRT出力パス
- `--concat`: 全体音声WAV出力パス

任意引数:

- `--gap`: 連続するセリフ間に挿入する無音秒数。既定値は `0.08`
- `--base_url`: VOICEVOX ENGINEのURL。既定値は `http://127.0.0.1:50021`

成功時は以下を表示する。

```txt
audio_path=all.wav
srt_path=output.srt
duration_sec=...
```

エラー時は `stderr` に以下の形式で表示し、終了コード `1` を返す。

```txt
error: ...
```

---

## 7. VOICEVOX話者alias

初期実装では固定aliasを使う。

```python
{"めたん": "四国めたん", "ずんだもん": "ずんだもん"}
```

alias設定ファイルやCLI引数化は未実装である。

---

## 8. WAV連結の仕様

`concatenate_wavs` は最初に登場した音声WAVの形式を基準にする。

確認する形式:

- チャンネル数
- サンプル幅
- サンプリング周波数

形式が一致しないWAVがあれば `ValueError` にする。

`SilenceEvent` は基準WAV形式に合わせて無音フレームとして連結する。

音声WAVが1つもない場合は `ValueError` にする。

---

## 9. SRT生成の仕様

`build_srt_cues` は `current_sec` を `0.0` から積み上げる。

- `DialogueEvent`: `SrtCue` を作る
- `SilenceEvent`: 時刻だけ進める
- `SoundEffectEvent`: 時刻だけ進める

字幕本文には `DialogueEvent.subtitle_text` を使う。

`format_srt_timestamp` は秒数を `HH:MM:SS,mmm` へ変換する。

`format_srt` は `SrtCue` のリストをSRT本文へ変換する。

`write_srt_file` はSRT本文をUTF-8で書き出す。

---

## 10. 現時点で未対応のこと

- 動画生成
- 字幕焼き込み
- 口パク
- 効果音の音量調整
- `fade_in` / `fade_out`
- セリフの `speed` / `pause` のVOICEVOX query反映
- `話者.スタイル` 指定
- aliases設定ファイル化
- aliasesのCLI引数化
- WAV形式の自動変換
- dry-run
- 詳細ログ
