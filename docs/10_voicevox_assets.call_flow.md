# 音声・字幕生成機能 呼び出し構成

## 1. エントリーポイント

初期実装の中心となるエントリーポイントは以下とする。

```python
run_voicevox_asset_pipeline(options: ScriptOptions) -> None
```

CLI層では、コマンドライン引数を `ScriptOptions` に変換してから、この関数を1回呼び出す。

想定するCLIの流れは以下。

1. `--script`、`--out_dir`、`--srt`、`--concat`、`--gap`、`--speed`、`--pause` などを受け取る。
2. 引数を検証し、`ScriptOptions` を作る。
3. `--show_speakers` が指定された場合は、VOICEVOX話者一覧を表示して終了する。
4. 通常実行では `run_voicevox_asset_pipeline(options)` を呼ぶ。
5. 例外が出た場合はCLI層で捕捉し、修正しやすいエラーメッセージを表示する。

---

## 2. 全体の処理順序

処理順序は以下で固定する。

```txt
read_script_file
  ↓
parse_script
  ↓
insert_gap_events
  ↓
synthesize_dialogue_wavs
  ↓
attach_sound_effect_info
  ↓
concatenate_wavs
  ↓
build_srt_cues
  ↓
write_srt_file
  ↓
print_summary
```

重要な制約は以下。

- SRT生成は、VOICEVOXでセリフWAVを生成し、各セリフのWAV長を取得した後に行う。
- 効果音の長さも、SRT生成前に取得しておく。
- `gap` は `insert_gap_events` で `SilenceEvent` としてイベント列へ挿入する。
- `concatenate_wavs` と `build_srt_cues` は、同じイベント列を参照する。
- `concatenate_wavs` と `build_srt_cues` は `default_gap` を受け取らない。
- `default_gap` を各関数で二重に加算しない。

---

## 3. 各工程で使う関数

### 3.1 台本ファイル読み込み

#### 呼び出し

```python
lines = read_script_file(options.script_path)
```

#### 役割

台本ファイルをUTF-8テキストとして読み込み、行リストにする。

#### 入力

- `options.script_path`

#### 出力

- `lines: list[str]`

#### この時点の状態

まだイベント化はしない。

コメント行、空行、セリフ行、間行、効果音行はすべて行テキストとして残っている。

---

### 3.2 台本解析

#### 呼び出し

```python
events = parse_script(lines, options.script_path.parent)
```

#### 役割

台本行をイベント列へ変換する。

#### 入力

- `lines`
- 台本ファイルのディレクトリ

#### 出力

- `events: list[ScriptEvent]`

#### この工程で作るイベント

- `DialogueEvent`
- `SilenceEvent(source="script")`
- `SoundEffectEvent`

#### この工程で無視するもの

- コメント行
- 空行

#### 注意

この時点では、通常のセリフ間gapはまだ入れない。

---

### 3.3 gapイベント挿入

#### 呼び出し

```python
events = insert_gap_events(events, options.default_gap)
```

#### 役割

`--gap` で指定された通常のセリフ間無音を、`SilenceEvent(source="gap")` としてイベント列へ挿入する。

#### 入力

- `events`
- `options.default_gap`

#### 出力

- gap用の `SilenceEvent` が追加された `events`

#### 注意

この工程以降、gapは単なるイベントとして扱う。

後続の `concatenate_wavs` と `build_srt_cues` は、gap秒数を自分で足さない。

---

### 3.4 セリフWAV生成

#### 呼び出し

```python
events = synthesize_dialogue_wavs(events, options)
```

#### 役割

`DialogueEvent` ごとにVOICEVOX APIを呼び出し、個別WAVを生成する。

#### 入力

- gap挿入済みの `events`
- `options`

#### 出力

- `DialogueEvent.wav_path`
- `DialogueEvent.duration_sec`

#### 内部で使う主な関数

- `fetch_voicevox_speakers`
- `resolve_speaker_id`
- `read_wav_info`

#### 注意

SRTの時刻計算に必要なセリフ長は、この工程で取得する。

台本の文字数や固定秒数から字幕時間を決めない。

---

### 3.5 効果音WAV情報取得

#### 呼び出し

```python
events = attach_sound_effect_info(events)
```

#### 役割

`SoundEffectEvent` のWAVファイルを確認し、長さを取得する。

#### 入力

- セリフWAV情報が付与済みの `events`

#### 出力

- `SoundEffectEvent.duration_sec`

#### 内部で使う主な関数

- `read_wav_info`

#### 注意

効果音はSRT字幕としては出さない。

ただし、効果音の長さは後続字幕の開始時刻に影響するため、SRT生成前に必ず取得する。

---

### 3.6 全体WAV連結

#### 呼び出し

```python
total_duration_sec = concatenate_wavs(events, options.concat_path)
```

#### 役割

同じイベント列を台本順に処理し、全体音声WAVを生成する。

#### 入力

- gapを含み、WAV長さ情報が付与済みの `events`
- `options.concat_path`

#### 出力

- `total_duration_sec`
- 全体音声WAVファイル

#### 連結対象

- `DialogueEvent`: 生成済みセリフWAV
- `SilenceEvent(source="script")`: 台本に明示された間
- `SilenceEvent(source="gap")`: `--gap` から挿入された通常gap
- `SoundEffectEvent`: 効果音WAV

#### 注意

この関数は `default_gap` を受け取らない。

gapはすでに `SilenceEvent` としてイベント列に含まれている。

---

### 3.7 SRT cue生成

#### 呼び出し

```python
cues = build_srt_cues(events)
```

#### 役割

イベント列の長さを台本順に積み上げ、セリフ字幕の開始時刻と終了時刻を決める。

#### 入力

- `concatenate_wavs` と同じ `events`

#### 出力

- `cues: list[SrtCue]`

#### cueを作るイベント

- `DialogueEvent`

#### cueを作らないが時刻に反映するイベント

- `SilenceEvent(source="script")`
- `SilenceEvent(source="gap")`
- `SoundEffectEvent`

#### 注意

この関数も `default_gap` を受け取らない。

SRT時刻は、セリフWAV長、効果音WAV長、間イベント秒数を同じイベント列から積み上げる。

---

### 3.8 SRTファイル書き出し

#### 呼び出し

```python
write_srt_file(cues, options.srt_path)
```

#### 役割

SRT cue一覧をSRT形式に整形し、ファイルへ保存する。

#### 入力

- `cues`
- `options.srt_path`

#### 出力

- SRTファイル

#### 注意

字幕本文には `DialogueEvent.subtitle_text` を使う。

VOICEVOXへ渡した `voice_text` と同一とは限らない。

---

### 3.9 ログ表示

#### 呼び出し

```python
print_summary(
    events=events,
    concat_path=options.concat_path,
    srt_path=options.srt_path,
    total_duration_sec=total_duration_sec,
    srt_count=len(cues),
)
```

#### 役割

最低限の処理結果を標準出力へ表示する。

#### 表示する情報

- 読み込んだイベント数
- 生成したセリフ音声数
- 使用した効果音数
- 出力した個別WAV件数
- 全体音声ファイルの出力先
- SRTファイルの出力先
- 全体音声の長さ
- SRT字幕件数

---

## 4. イベント列の変化

### 4.1 台本読み込み直後

`read_script_file` の出力は、まだ文字列リスト。

```txt
[
  "ずんだもん：印刷開始、うるさくないのだ？",
  "",
  "めたん：あーそれ",
  "印刷開始の振動でしょ",
  "(間 0.25)",
  "(SE se\\pop.wav)",
  "めたん：原因は、印刷開始時の振動ね"
]
```

### 4.2 parse_script 後

コメント行と空行は消える。

台本上の意味を持つ行だけがイベントになる。

```txt
[
  DialogueEvent(line_no=1, speaker="ずんだもん", duration_sec=None, wav_path=None),
  DialogueEvent(line_no=3, speaker="めたん", duration_sec=None, wav_path=None),
  DialogueEvent(line_no=4, speaker="めたん", duration_sec=None, wav_path=None),
  SilenceEvent(line_no=5, duration_sec=0.25, source="script"),
  SoundEffectEvent(line_no=6, path="se\\pop.wav", duration_sec=None),
  DialogueEvent(line_no=7, speaker="めたん", duration_sec=None, wav_path=None)
]
```

### 4.3 insert_gap_events 後

通常gapが `SilenceEvent(source="gap")` として挿入される。

```txt
[
  DialogueEvent(line_no=1, duration_sec=None),
  SilenceEvent(line_no=None, duration_sec=0.08, source="gap"),
  DialogueEvent(line_no=3, duration_sec=None),
  SilenceEvent(line_no=None, duration_sec=0.08, source="gap"),
  DialogueEvent(line_no=4, duration_sec=None),
  SilenceEvent(line_no=5, duration_sec=0.25, source="script"),
  SoundEffectEvent(line_no=6, duration_sec=None),
  DialogueEvent(line_no=7, duration_sec=None)
]
```

実際にどこへgapを入れるかは `insert_gap_events` の仕様に従う。

重要なのは、gapをこの段階でイベント化し、以降は追加加算しないこと。

### 4.4 synthesize_dialogue_wavs 後

セリフイベントに個別WAVパスとWAV長が入る。

```txt
[
  DialogueEvent(line_no=1, wav_path="wav/001_ずんだもん_....wav", duration_sec=1.42),
  SilenceEvent(source="gap", duration_sec=0.08),
  DialogueEvent(line_no=3, wav_path="wav/002_めたん_....wav", duration_sec=0.74),
  SilenceEvent(source="gap", duration_sec=0.08),
  DialogueEvent(line_no=4, wav_path="wav/003_めたん_....wav", duration_sec=1.10),
  SilenceEvent(source="script", duration_sec=0.25),
  SoundEffectEvent(line_no=6, duration_sec=None),
  DialogueEvent(line_no=7, wav_path="wav/004_めたん_....wav", duration_sec=1.35)
]
```

### 4.5 attach_sound_effect_info 後

効果音イベントにもWAV長が入る。

```txt
[
  DialogueEvent(duration_sec=1.42),
  SilenceEvent(source="gap", duration_sec=0.08),
  DialogueEvent(duration_sec=0.74),
  SilenceEvent(source="gap", duration_sec=0.08),
  DialogueEvent(duration_sec=1.10),
  SilenceEvent(source="script", duration_sec=0.25),
  SoundEffectEvent(duration_sec=0.31),
  DialogueEvent(duration_sec=1.35)
]
```

この状態が、WAV連結とSRT生成で共有する完成イベント列になる。

### 4.6 concatenate_wavs と build_srt_cues が見るイベント列

両方とも同じ完成イベント列を見る。

```txt
completed_events
  ├─ concatenate_wavs(completed_events, concat_path)
  └─ build_srt_cues(completed_events)
```

ここで別々にgapを足したり、片方だけ効果音長を無視したりしない。

---

## 5. SRT生成に必要な前提

`build_srt_cues(events)` を呼ぶ前に、以下が満たされている必要がある。

- `events` は `insert_gap_events` 済みである。
- すべての `DialogueEvent` に `wav_path` が設定されている。
- すべての `DialogueEvent` に `duration_sec` が設定されている。
- すべての `SoundEffectEvent` に `duration_sec` が設定されている。
- `SilenceEvent` は `duration_sec` を持っている。
- `DialogueEvent.subtitle_text` が空でない。
- SRT時刻計算に `default_gap` を追加で渡さない。

SRT cueの作成ルールは以下。

```txt
current = 0.0

for event in events:
  if DialogueEvent:
    start = current
    end = current + event.duration_sec
    cue = SrtCue(start, end, event.subtitle_text)
    current = end

  if SilenceEvent:
    current += event.duration_sec

  if SoundEffectEvent:
    current += event.duration_sec
```

字幕として出るのは `DialogueEvent` だけ。

ただし、`SilenceEvent` と `SoundEffectEvent` は時刻計算に必ず含める。

---

## 6. エラー時の扱い

### 6.1 基本方針

各工程で発生したエラーは握りつぶさず、上位へ伝播する。

CLI層で捕捉して、ユーザーが台本や環境を修正しやすい形で表示する。

可能な限り以下を含める。

- 台本の行番号
- 該当する話者名
- 該当するファイルパス
- 失敗した工程
- 修正の手がかり

例。

```txt
5行目: 話者 'めたん' がVOICEVOX話者一覧に見つかりません
```

### 6.2 工程別の主なエラー

#### read_script_file

- 台本ファイルが存在しない
- 台本ファイルを読み込めない

#### parse_script

- 話者省略セリフの前に話者が存在しない
- 間の秒数が不正
- 効果音パスが空
- 個別パラメータ形式が不正
- 未対応パラメータが指定された

#### insert_gap_events

- `gap_sec` が負数

#### synthesize_dialogue_wavs

- VOICEVOXに接続できない
- 指定された話者が見つからない
- audio query作成に失敗した
- synthesisに失敗した
- 個別WAVを書き込めない
- 生成済みWAVの長さを取得できない

#### attach_sound_effect_info

- 効果音ファイルが存在しない
- 効果音ファイルがWAV形式ではない
- 効果音WAVの長さを取得できない
- 初期実装で未対応の効果音パラメータが指定された

#### concatenate_wavs

- セリフWAVが存在しない
- 効果音WAVが存在しない
- WAV形式が一致しない
- 全体WAVを書き込めない
- セリフまたは効果音の `duration_sec` が未設定

#### build_srt_cues

- セリフWAV長が未設定
- 効果音WAV長が未設定
- 字幕文が空
- 未知のイベント種別がある

#### write_srt_file

- SRT時刻範囲が不正
- SRTファイルを書き込めない

---

## 7. レビュー観点

### 7.1 呼び出し順序

- `build_srt_cues` が `synthesize_dialogue_wavs` より前に呼ばれていないか。
- `build_srt_cues` が `attach_sound_effect_info` より前に呼ばれていないか。
- `concatenate_wavs` と `build_srt_cues` が同じ完成イベント列を参照しているか。

### 7.2 gapの扱い

- `insert_gap_events` 以外で `default_gap` を加算していないか。
- `concatenate_wavs` が `default_gap` を受け取っていないか。
- `build_srt_cues` が `default_gap` を受け取っていないか。
- gapが `SilenceEvent(source="gap")` としてイベント列に一度だけ入っているか。

### 7.3 SRT時刻

- SRT時刻が生成済みWAVの長さをもとに計算されているか。
- 台本の文字数や固定秒数からセリフ表示時間を決めていないか。
- 間と効果音がSRT本文には出ず、時刻計算には含まれているか。
- 字幕本文に `subtitle_text` を使っているか。

### 7.4 WAV連結

- セリフ、間、gap、効果音がイベント列の順に連結されているか。
- 効果音WAVの形式チェックが行われているか。
- WAV形式が一致しない場合にエラーになるか。
- 効果音の `volume`、`fade_in`、`fade_out` を初期実装で無理に加工していないか。

### 7.5 エラー表示

- 台本由来のエラーに行番号が含まれているか。
- VOICEVOX接続失敗が分かりやすいか。
- 話者未解決時に、どの話者が見つからなかったか分かるか。
- ファイル入出力エラーで対象パスが表示されるか。

### 7.6 対象外範囲

- 動画生成をこの呼び出し構成に混ぜていないか。
- 画像切り替えを実装対象にしていないか。
- 字幕焼き込み、BGM追加、GUI化を混ぜていないか。

---

## 8. 最小の擬似コード

実装時の呼び出し形は、おおむね以下を想定する。

```python
def run_voicevox_asset_pipeline(options: ScriptOptions) -> None:
    lines = read_script_file(options.script_path)

    events = parse_script(
        lines=lines,
        script_dir=options.script_path.parent,
    )

    events = insert_gap_events(
        events=events,
        gap_sec=options.default_gap,
    )

    events = synthesize_dialogue_wavs(
        events=events,
        options=options,
    )

    events = attach_sound_effect_info(events)

    total_duration_sec = concatenate_wavs(
        events=events,
        output_path=options.concat_path,
    )

    cues = build_srt_cues(events)

    write_srt_file(
        cues=cues,
        srt_path=options.srt_path,
    )

    print_summary(
        events=events,
        concat_path=options.concat_path,
        srt_path=options.srt_path,
        total_duration_sec=total_duration_sec,
        srt_count=len(cues),
    )
```

この擬似コードでは、`events` が段階的に情報を持つようになり、最後の `events` を `concatenate_wavs` と `build_srt_cues` が共有する。
