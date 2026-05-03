# 音声・字幕生成機能 関数設計

## 1. 前提

本設計は `docs/10_voicevox_assets.md` の仕様を、Pythonで初期実装しやすい粒度の関数仕様へ分解したものである。

対象範囲は以下に限定する。

- 台本ファイルの読み込み
- 台本のイベント列への解析
- 通常のセリフ間gapのイベント化
- VOICEVOXによるセリフ別WAV生成
- 生成済みWAVと効果音WAVの情報取得
- セリフ音声、間、効果音のWAV連結
- 生成済みWAVの長さをもとにしたSRT生成

以下は対象外とする。

- 動画ファイル生成
- 画像切り替え
- 字幕焼き込み
- BGM追加
- GUI化

台本は将来の画像切り替えイベントなどを追加しやすいように、行の集合ではなくイベント列として扱う。

---

## 2. 設計方針

### 2.1 関数粒度

初期実装では、個人ツールとして扱いやすい粒度を優先する。

そのため、以下のような細かい補助関数は、必要になった段階で切り出す。

- WAV情報から長さだけを返す関数
- 汎用テキスト書き込み関数
- ログ集計とログ出力の分離
- PCMフレームの音量、フェード加工関数

本設計では、レビュー対象として意味のある主関数を中心に定義する。

### 2.2 gapの扱い

`--gap` で指定する通常のセリフ間無音は、台本解析後に `SilenceEvent` としてイベント列へ挿入する。

これにより、WAV連結とSRT時刻計算は同じイベント列だけを参照できる。

`concatenate_wavs` や `build_srt_cues` は `default_gap` を受け取らない。gapを直接加算しない。

この方針により、全体音声に入るgapとSRT時刻に反映されるgapの二重加算やズレを防ぐ。

### 2.3 効果音パラメータの扱い

初期実装では、効果音WAVはそのまま連結する。

`volume`、`fade_in`、`fade_out` は台本上のパラメータとして解析と検証は行うが、第1段階では未適用として扱う。

実装時は以下のどちらかを選ぶ。

- パラメータが指定された場合に「未対応」として分かりやすくエラーにする
- パラメータを保持だけしてログに警告を出し、音声加工は行わない

音量やフェード加工は、WAV連結が安定した後の拡張対象とする。

---

## 3. 想定データ構造

実装時は `dataclass` などで表現することを想定する。

### ScriptOptions

- `script_path: Path`
- `out_dir: Path`
- `srt_path: Path`
- `concat_path: Path`
- `voicevox_url: str`
- `default_gap: float`
- `default_speed: float`
- `default_pause: float | None`
- `speaker_aliases: dict[str, str]`

### DialogueEvent

- `line_no: int`
- `speaker: str`
- `voice_text: str`
- `subtitle_text: str`
- `params: dict[str, str]`
- `wav_path: Path | None`
- `duration_sec: float | None`

### SilenceEvent

- `line_no: int | None`
- `duration_sec: float`
- `source: str`

`source` は `"script"` または `"gap"` を想定する。台本に明示された間と、`--gap` から挿入された無音を区別するために使う。

### SoundEffectEvent

- `line_no: int`
- `path: Path`
- `params: dict[str, str]`
- `duration_sec: float | None`

### WavInfo

- `channels: int`
- `sample_width: int`
- `frame_rate: int`
- `frame_count: int`
- `duration_sec: float`

### SrtCue

- `index: int`
- `start_sec: float`
- `end_sec: float`
- `text: str`

### ScriptEvent

`DialogueEvent | SilenceEvent | SoundEffectEvent`

---

## 4. 関数仕様

### read_script_file

#### 関数名

`read_script_file(script_path: Path) -> list[str]`

#### 目的

台本ファイルを読み込み、行単位の文字列リストとして返す。

#### 入力

- `script_path`: 台本ファイルのパス

#### 出力

- 台本ファイルの各行を格納した `list[str]`

#### 処理概要

1. `script_path` が存在するか確認する。
2. ファイルとして読み込み可能か確認する。
3. UTF-8で読み込む。
4. 改行文字を除いた行リストを返す。

#### 依存関係

- `pathlib.Path`

#### エラー方針

- ファイルが存在しない場合は、台本ファイルが見つからないことを示す例外を送出する。
- 読み込みに失敗した場合は、対象パスを含む例外を送出する。

#### テスト観点

- 存在する台本ファイルを読み込める。
- 存在しないファイルでエラーになる。
- 空行やコメント行も、この段階ではそのまま読み込まれる。

---

### parse_script

#### 関数名

`parse_script(lines: list[str], script_dir: Path) -> list[ScriptEvent]`

#### 目的

台本の行リストを、セリフ、間、効果音のイベント列へ変換する。

#### 入力

- `lines`: 台本ファイルの行リスト
- `script_dir`: 台本ファイルが存在するディレクトリ

#### 出力

- `list[ScriptEvent]`

#### 処理概要

1. 行を先頭から順に処理する。
2. 空行とコメント行は無視する。
3. `(間 0.25)` 形式の行は `SilenceEvent` にする。
4. `(SE se\pop.wav)` 形式の行は `SoundEffectEvent` にする。
5. それ以外は `DialogueEvent` として扱う。
6. セリフ行は、全角コロンまたは半角コロンで話者と本文を分離する。
7. 話者省略セリフでは、直前の話者を引き継ぐ。
8. `||` があれば、左側を読み上げ用テキスト、右側を字幕用テキストにする。
9. 行末の `{key=value}` 形式の個別パラメータを解析する。
10. イベント列を台本順に返す。

#### 依存関係

- `pathlib.Path`
- `re`
- 個別パラメータ検証処理

#### エラー方針

- 話者省略セリフの前に話者が存在しない場合は、行番号つきで例外を送出する。
- 間の秒数が不正な場合は、行番号つきで例外を送出する。
- 効果音パスが空の場合は、行番号つきで例外を送出する。
- 個別パラメータ形式が不正な場合は、行番号つきで例外を送出する。
- 未対応パラメータが指定された場合は、行番号つきで例外を送出する。

#### テスト観点

- 話者つきセリフを解析できる。
- 半角コロンの話者指定を解析できる。
- 話者省略時に直前の話者を引き継げる。
- 直前話者がない話者省略セリフはエラーになる。
- 読み上げ文と字幕文を `||` で分離できる。
- `||` がない場合は読み上げ文と字幕文が同一になる。
- 間イベントを解析できる。
- 効果音イベントを解析できる。
- コメント行と空行が無視される。
- 個別パラメータを解析できる。
- 不明な個別パラメータはエラーになる。

---

### insert_gap_events

#### 関数名

`insert_gap_events(events: list[ScriptEvent], gap_sec: float) -> list[ScriptEvent]`

#### 目的

通常のセリフ間無音を `SilenceEvent` としてイベント列へ挿入する。

#### 入力

- `events`: 台本から解析したイベント列
- `gap_sec`: 通常のセリフ間無音秒数

#### 出力

- gap用の `SilenceEvent` が挿入されたイベント列

#### 処理概要

1. `gap_sec` が0以下の場合は、元のイベント列を返す。
2. イベント列を先頭から確認する。
3. セリフイベントの直後に、次の音声系イベントが続く場合、`SilenceEvent(source="gap")` を挿入する。
4. 台本に明示された `(間 ...)` はそのまま保持する。
5. 挿入後のイベント列を返す。

「音声系イベント」は、初期実装では `DialogueEvent` と `SoundEffectEvent` を指す。

#### 依存関係

- `ScriptEvent`
- `SilenceEvent`

#### エラー方針

- `gap_sec` が負数の場合は例外を送出する。

#### テスト観点

- セリフ間にgap用の `SilenceEvent` が挿入される。
- `gap_sec` が0の場合は挿入されない。
- 明示的な間イベントとgapイベントを区別できる。
- WAV連結とSRT生成が同じgapイベントを参照できる。
- gapが二重に加算されない。

---

### fetch_voicevox_speakers

#### 関数名

`fetch_voicevox_speakers(base_url: str) -> list[dict]`

#### 目的

VOICEVOX APIから利用可能な話者一覧を取得する。

#### 入力

- `base_url`: VOICEVOXエンジンのURL

#### 出力

- VOICEVOX APIの話者一覧レスポンス

#### 処理概要

1. `GET /speakers` を呼び出す。
2. レスポンスステータスを確認する。
3. JSONとして解析して返す。

#### 依存関係

- HTTPクライアントライブラリ
- VOICEVOX API

#### エラー方針

- 接続できない場合は、VOICEVOXに接続できないことを示す例外を送出する。
- HTTPエラーの場合は、ステータスコードを含む例外を送出する。
- JSON解析に失敗した場合は、レスポンス形式が不正であることを示す例外を送出する。

#### テスト観点

- 正常な話者一覧を取得できる。
- 接続失敗時に分かりやすいエラーになる。
- HTTPエラー時に分かりやすいエラーになる。

---

### resolve_speaker_id

#### 関数名

`resolve_speaker_id(speaker_name: str, speakers: list[dict], aliases: dict[str, str]) -> int`

#### 目的

台本上の話者名をVOICEVOXの話者IDへ解決する。

#### 入力

- `speaker_name`: 台本上の話者名
- `speakers`: VOICEVOXの話者一覧
- `aliases`: 台本名からVOICEVOX名への別名対応

#### 出力

- VOICEVOX APIに渡す `speaker` ID

#### 処理概要

1. `aliases` に話者名があれば、対応先の名前に置き換える。
2. VOICEVOX話者一覧から一致する話者またはスタイルを検索する。
3. 対応するスタイルIDを返す。

#### 依存関係

- `fetch_voicevox_speakers` の取得結果

#### エラー方針

- 話者が見つからない場合は、話者名を含む例外を送出する。
- 同名候補が複数あり解決できない場合は、候補情報を含む例外を送出する。

#### テスト観点

- 完全一致する話者を解決できる。
- 別名対応で話者を解決できる。
- 存在しない話者でエラーになる。

---

### synthesize_dialogue_wavs

#### 関数名

`synthesize_dialogue_wavs(events: list[ScriptEvent], options: ScriptOptions) -> list[ScriptEvent]`

#### 目的

セリフイベントに対してVOICEVOX音声を生成し、個別WAVとして保存する。

#### 入力

- `events`: gap挿入済みのイベント列
- `options`: 実行オプション

#### 出力

- セリフイベントに `wav_path` と `duration_sec` が設定されたイベント列

#### 処理概要

1. VOICEVOXの話者一覧を取得する。
2. イベント列から `DialogueEvent` だけを順に処理する。
3. 話者名を `resolve_speaker_id` でVOICEVOX話者IDへ解決する。
4. `POST /audio_query` を呼び出し、audio queryを作成する。
5. `default_speed`、`default_pause`、セリフ個別パラメータをaudio queryへ反映する。
6. `POST /synthesis` を呼び出し、WAVバイト列を取得する。
7. セリフ番号、話者名、本文から個別WAVパスを作る。
8. 個別WAVを保存する。
9. 保存したWAVの情報を `read_wav_info` で取得し、`duration_sec` をセリフイベントへ設定する。
10. 元のイベント順を保ったまま返す。

#### 依存関係

- `fetch_voicevox_speakers`
- `resolve_speaker_id`
- VOICEVOX API
- `read_wav_info`
- `pathlib.Path`

#### エラー方針

- VOICEVOX接続失敗、話者未解決、音声生成失敗、保存失敗、WAV情報取得失敗は行番号つきで例外を送出する。
- 途中で失敗した場合、どのセリフで失敗したか分かるメッセージにする。

#### テスト観点

- セリフイベントだけVOICEVOX連携対象になる。
- 間イベントと効果音イベントは変更されずに残る。
- 生成済みWAVの長さがセリフイベントに設定される。
- 読み上げ用テキストがVOICEVOXへ渡される。
- 字幕用テキストはVOICEVOXへ渡されない。
- VOICEVOX依存をモックしてテストできる。

---

### read_wav_info

#### 関数名

`read_wav_info(path: Path) -> WavInfo`

#### 目的

WAVファイルの形式情報と長さを取得する。

#### 入力

- `path`: WAVファイルパス

#### 出力

- `WavInfo`

#### 処理概要

1. ファイルの存在を確認する。
2. WAVとして開く。
3. チャンネル数、サンプル幅、サンプリング周波数、フレーム数を取得する。
4. `frame_count / frame_rate` で秒数を計算する。
5. `WavInfo` として返す。

#### 依存関係

- `wave`
- `pathlib.Path`

#### エラー方針

- ファイルが存在しない場合は、対象パスを含む例外を送出する。
- WAVとして開けない場合は、WAV形式ではないことを示す例外を送出する。
- 長さを計算できない場合は例外を送出する。

#### テスト観点

- 正常なWAVの形式情報を取得できる。
- 秒単位の長さを取得できる。
- 存在しないファイルでエラーになる。
- WAVでないファイルでエラーになる。

---

### attach_sound_effect_info

#### 関数名

`attach_sound_effect_info(events: list[ScriptEvent]) -> list[ScriptEvent]`

#### 目的

効果音イベントにWAVファイルの長さを付与する。

#### 入力

- `events`: イベント列

#### 出力

- 効果音イベントに `duration_sec` が設定されたイベント列

#### 処理概要

1. イベント列から `SoundEffectEvent` を取り出す。
2. 各効果音ファイルについて `read_wav_info` を呼び出す。
3. `duration_sec` を効果音イベントへ設定する。
4. 元のイベント順を保って返す。

初期実装では、`volume`、`fade_in`、`fade_out` は音声へ反映しない。

#### 依存関係

- `read_wav_info`

#### エラー方針

- 効果音ファイルが存在しない場合は、行番号つきで例外を送出する。
- 効果音ファイルがWAV形式でない場合は、行番号つきで例外を送出する。
- 効果音パラメータを第1段階で未対応とする場合は、該当パラメータが指定された時点で行番号つきの未対応エラーにする。

#### テスト観点

- 効果音イベントに長さが設定される。
- セリフイベントと間イベントは変更されない。
- 存在しない効果音ファイルでエラーになる。
- 効果音パラメータの初期実装方針に沿って、未対応エラーまたは警告扱いになる。

---

### concatenate_wavs

#### 関数名

`concatenate_wavs(events: list[ScriptEvent], output_path: Path) -> float`

#### 目的

イベント列を台本順に処理し、セリフ音声、間、効果音を連結した全体音声WAVを出力する。

#### 入力

- `events`: gapを含み、WAV長さ情報が付与済みのイベント列
- `output_path`: 全体音声WAVの出力先

#### 出力

- 全体音声の長さ秒数

#### 処理概要

1. 最初のセリフWAVまたは効果音WAVから基準WAV形式を決める。
2. 出力WAVを基準形式で開く。
3. イベント列を順に処理する。
4. `DialogueEvent` では、生成済みWAVのフレームを書き込む。
5. `SilenceEvent` では、指定秒数の無音フレームを書き込む。
6. `SoundEffectEvent` では、効果音WAVを読み込み、形式を検証して、そのまま書き込む。
7. 書き込んだ総フレーム数から全体音声の長さを返す。

この関数は `default_gap` を受け取らない。gapは事前に `insert_gap_events` で `SilenceEvent` としてイベント列へ入れておく。

#### 依存関係

- `read_wav_info`
- `wave`
- 無音フレーム生成処理

#### エラー方針

- 連結対象WAVが存在しない場合は、行番号つきで例外を送出する。
- WAV形式が一致しない場合は、行番号または対象ファイルを含む例外を送出する。
- 出力先に書き込めない場合は、出力パスを含む例外を送出する。
- セリフイベントの `wav_path` や `duration_sec` が未設定の場合はエラーにする。

#### テスト観点

- セリフ音声が台本順に連結される。
- 明示的な間が無音として連結される。
- gapイベントが無音として連結される。
- 効果音がそのまま連結される。
- 効果音の形式不一致でエラーになる。
- 連結結果の長さが各イベント長の合計と一致する。
- gapがこの関数内で追加加算されない。

---

### build_srt_cues

#### 関数名

`build_srt_cues(events: list[ScriptEvent]) -> list[SrtCue]`

#### 目的

イベント列の長さを台本順に積み上げ、セリフ字幕の開始時刻と終了時刻を決定する。

#### 入力

- `events`: gapを含み、WAV長さ情報が付与済みのイベント列

#### 出力

- `list[SrtCue]`

#### 処理概要

1. 現在時刻を `0.0` で初期化する。
2. イベント列を台本順に処理する。
3. `DialogueEvent` の場合、現在時刻を開始時刻、現在時刻 + セリフWAV長を終了時刻としてSRT cueを作る。
4. 字幕文には `subtitle_text` を使う。
5. `SilenceEvent` と `SoundEffectEvent` はcueを作らず、現在時刻だけ進める。
6. 各イベントの長さは、生成済みWAVの長さ、効果音WAVの長さ、または間イベントの秒数から取得する。

この関数は `default_gap` を受け取らない。gapはすでに `SilenceEvent` としてイベント列に含まれている前提とする。

#### 依存関係

- `ScriptEvent`

#### エラー方針

- セリフまたは効果音の長さが未設定の場合は例外を送出する。
- 字幕文が空の場合は、行番号つきで例外を送出する。
- 未知のイベント種別は例外にする。

#### テスト観点

- セリフイベントだけcueになる。
- 明示的な間はcueにならないが、後続字幕の開始時刻を遅らせる。
- gapイベントはcueにならないが、後続字幕の開始時刻を遅らせる。
- 効果音イベントはcueにならないが、後続字幕の開始時刻を遅らせる。
- SRT時刻が生成済みWAVの長さをもとに計算される。
- 台本の文字数や固定秒数で字幕時間を決めていない。
- 字幕文には `subtitle_text` が使われる。
- gapがこの関数内で追加加算されない。

---

### write_srt_file

#### 関数名

`write_srt_file(cues: list[SrtCue], srt_path: Path) -> None`

#### 目的

SRT cue一覧をSRT形式へ整形し、ファイルへ保存する。

#### 入力

- `cues`: SRT cue一覧
- `srt_path`: SRT出力先

#### 出力

- なし

#### 処理概要

1. cueを順に処理する。
2. 連番、時刻範囲、字幕文、空行の形式で文字列化する。
3. 秒数を `HH:MM:SS,mmm` 形式へ変換する。
4. 出力先ディレクトリを作成する。
5. UTF-8でSRTファイルを書き込む。

#### 依存関係

- `pathlib.Path`

#### エラー方針

- 終了時刻が開始時刻より前のcueはエラーにする。
- 字幕文が空のcueはエラーにする。
- 書き込みに失敗した場合は、出力先パスを含む例外を送出する。

#### テスト観点

- SRT形式のファイルを書き出せる。
- 複数cueを連番で出力できる。
- 時刻表記がSRT形式になる。
- 不正な時刻範囲でエラーになる。

---

### print_summary

#### 関数名

`print_summary(events: list[ScriptEvent], concat_path: Path, srt_path: Path, total_duration_sec: float, srt_count: int) -> None`

#### 目的

処理結果の最低限のログを標準出力へ表示する。

#### 入力

- `events`: 処理済みイベント列
- `concat_path`: 全体音声ファイルの出力先
- `srt_path`: SRTファイルの出力先
- `total_duration_sec`: 全体音声の長さ
- `srt_count`: SRT字幕件数

#### 出力

- なし

#### 処理概要

1. 読み込んだイベント数を表示する。
2. 生成したセリフ音声数を表示する。
3. 使用した効果音数を表示する。
4. 出力した個別WAV件数を表示する。
5. 全体音声ファイルの出力先を表示する。
6. SRTファイルの出力先を表示する。
7. 全体音声の長さとSRT字幕件数を表示する。

#### 依存関係

- 標準出力

#### エラー方針

- 原則として例外は送出しない。

#### テスト観点

- 必要な項目が表示される。
- セリフ数、効果音数、SRT件数が確認できる。

---

### run_voicevox_asset_pipeline

#### 関数名

`run_voicevox_asset_pipeline(options: ScriptOptions) -> None`

#### 目的

台本読み込みから、個別WAV生成、全体WAV生成、SRT生成までの一連の処理を実行する。

#### 入力

- `options`: 実行オプション

#### 出力

- なし

#### 処理概要

1. `read_script_file` で台本を読み込む。
2. `parse_script` でイベント列に変換する。
3. `insert_gap_events` で通常gapを `SilenceEvent` として挿入する。
4. `synthesize_dialogue_wavs` でセリフ別WAVを生成し、長さを付与する。
5. `attach_sound_effect_info` で効果音WAVの長さを付与する。
6. `concatenate_wavs` で全体音声WAVを生成する。
7. `build_srt_cues` でSRT cueを生成する。
8. `write_srt_file` でSRT字幕を書き出す。
9. `print_summary` で処理結果を表示する。

#### 依存関係

- `read_script_file`
- `parse_script`
- `insert_gap_events`
- `synthesize_dialogue_wavs`
- `attach_sound_effect_info`
- `concatenate_wavs`
- `build_srt_cues`
- `write_srt_file`
- `print_summary`

#### エラー方針

- 各工程の例外を握りつぶさず、上位へ伝播する。
- 例外には可能な限り台本行番号、対象ファイル、話者名など修正に必要な情報を含める。
- CLI層ではこの例外を捕捉し、ユーザーに分かりやすいメッセージとして表示する。

#### テスト観点

- 各関数が正しい順序で呼ばれる。
- セリフ、間、効果音を含む台本から全成果物を生成できる。
- gapがイベント列に一度だけ挿入される。
- WAV連結とSRT生成が同じイベント列を参照する。
- SRT時刻が全体音声の進行と一致する。
- VOICEVOX連携部分をモックしてパイプラインをテストできる。
- エラー時に該当工程で処理が止まる。

---

## 5. 初期実装で切り出してもよい補助関数

以下は、実装時にコードが読みづらくなった場合だけ切り出す。

- `parse_inline_params(text, line_no)`
- `validate_params(params, allowed_keys, line_no)`
- `sanitize_filename_part(text)`
- `format_srt_timestamp(seconds)`
- `create_silence_frames(duration_sec, wav_info)`
- `validate_wav_compatibility(reference, target, path)`

これらは独立関数にしてもよいが、初期設計レビューの中心にはしない。

---

## 6. 責務分離の確認

- 台本解析は `parse_script` に閉じる。
- gapは `insert_gap_events` でイベント化し、それ以降の関数では追加計算しない。
- VOICEVOX依存は `fetch_voicevox_speakers`、`resolve_speaker_id`、`synthesize_dialogue_wavs` に閉じる。
- WAV情報取得は `read_wav_info` に集約する。
- WAV連結は `concatenate_wavs` に閉じる。
- SRT時刻計算は `build_srt_cues` に閉じる。
- SRT書き出しは `write_srt_file` に閉じる。
- SRT時刻は必ず生成済みWAVと効果音WAVの長さ、間イベントの秒数を積み上げて決める。
- 間と効果音はSRT本文には出さないが、SRT時刻計算には含める。
- 効果音の `volume`、`fade_in`、`fade_out` は初期実装では音声加工しない。
- 将来の画像切り替えイベントは、`ScriptEvent` に新しいイベント型を追加し、WAV連結やSRT生成側では必要に応じて時間だけ反映または無視する方針とする。
