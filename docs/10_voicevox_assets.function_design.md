# 音声・字幕生成機能 関数設計

## 1. 前提

本ドキュメントは、現在の `make_voicevox_assets.py` に実装済みの関数を整理した設計メモである。

今後の構想ではなく、第1章時点で存在する実装だけを対象にする。

---

## 2. データ構造

### ScriptOptions

CLIおよび `generate_voicevox_assets` に渡す実行オプション。

- `script_path: Path`
- `out_dir: Path`
- `srt_path: Path`
- `concat_path: Path`
- `voicevox_url: str`
- `default_gap: float`
- `default_speed: float`
- `default_pause: float | None`
- `speaker_aliases: dict[str, str]`

`default_speed` と `default_pause` は現時点ではVOICEVOX queryへ反映していない。

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

`source` は主に `"script"` または `"gap"`。

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

## 3. 固定値

### DEFAULT_SPEAKER_ALIASES

#### 役割

初期実装の固定話者alias。

#### 内容

```python
{"めたん": "四国めたん", "ずんだもん": "ずんだもん"}
```

#### 外部依存

なし。

#### テスト方針

`generate_voicevox_assets` と `main` のテストで、`synthesize_dialogue_wavs` または `ScriptOptions` に渡ることを確認する。

---

## 4. 関数仕様

### read_script_file

`read_script_file(script_path: Path) -> list[str]`

- 役割: UTF-8の台本ファイルを読み、改行を除いた行リストを返す。
- 入力: 台本ファイルパス。
- 出力: `list[str]`。
- 主なエラー: ファイルなし、ファイルでない、読み込み失敗。
- 外部依存: ファイルシステム。
- テスト方針: `tmp_path` で正常読み込み、存在しないファイル、空行・コメント保持を確認する。

### parse_script

`parse_script(lines: list[str], script_dir: Path) -> list[ScriptEvent]`

- 役割: 台本行を `DialogueEvent` / `SilenceEvent` / `SoundEffectEvent` に変換する。
- 入力: 行リスト、台本ディレクトリ。
- 出力: `list[ScriptEvent]`。
- 主なエラー: 話者省略の前話者なし、空本文、空voice/subtitle、不正な間、不正な効果音、不正な個別パラメータ、未対応パラメータ。
- 外部依存: なし。効果音ファイルの存在確認はしない。
- テスト方針: セリフ、話者省略、`||`、間、効果音、コメント・空行、個別パラメータ、各種不正入力を確認する。

### insert_gap_events

`insert_gap_events(events: list[ScriptEvent], gap_sec: float) -> list[ScriptEvent]`

- 役割: 連続する `DialogueEvent` 同士の間に `SilenceEvent(source="gap")` を挿入する。
- 入力: イベント列、gap秒数。
- 出力: gap挿入後のイベント列。
- 主なエラー: `gap_sec` が負数。
- 外部依存: なし。
- テスト方針: 連続セリフ間の挿入、非セリフを挟む場合、0秒、空リスト、単一イベント、負数を確認する。

### read_wav_info

`read_wav_info(path: Path) -> WavInfo`

- 役割: WAV形式情報と長さを取得する。
- 入力: WAVファイルパス。
- 出力: `WavInfo`。
- 主なエラー: ファイルなし、ファイルでない、WAVとして読めない、サンプリング周波数不正。
- 外部依存: ファイルシステム、`wave`。
- テスト方針: `wave` で作った小さいWAV、存在しないファイル、非WAV、duration計算を確認する。

### fetch_voicevox_speakers

`fetch_voicevox_speakers(base_url: str) -> list[dict]`

- 役割: VOICEVOX ENGINEの `/speakers` を取得する。
- 入力: VOICEVOX ENGINE base URL。
- 出力: 話者一覧の `list[dict]`。
- 主なエラー: 接続失敗、HTTPエラー、不正JSON、不正なJSON形。
- 外部依存: VOICEVOX ENGINE、HTTP。
- テスト方針: `urllib.request.urlopen` をmonkeypatchして、正常、末尾スラッシュ、接続失敗、HTTPエラー、不正JSONを確認する。

### resolve_speaker_id

`resolve_speaker_id(speaker_name: str, speakers: list[dict], aliases: dict[str, str]) -> int`

- 役割: 台本上の話者名をVOICEVOX style idへ解決する。
- 入力: 台本話者名、話者一覧、alias。
- 出力: style id。
- 主なエラー: 話者なし、styles空、style idなし、style id不正。
- 外部依存: なし。`speakers` は呼び出し側から渡す。
- テスト方針: 一致、alias、話者なし、styles空、style idなしを確認する。

### create_audio_query

`create_audio_query(base_url: str, text: str, speaker_id: int) -> dict`

- 役割: VOICEVOX ENGINEの `/audio_query` をPOSTし、audio queryを作る。
- 入力: base URL、読み上げテキスト、speaker id。
- 出力: audio queryのdict。
- 主なエラー: 接続失敗、HTTPエラー、不正JSON、不正なJSON形。
- 外部依存: VOICEVOX ENGINE、HTTP。
- テスト方針: `urlopen` をmonkeypatchし、POST先、query、JSON返却、各種失敗を確認する。

### synthesize_wav

`synthesize_wav(base_url: str, audio_query: dict, speaker_id: int) -> bytes`

- 役割: VOICEVOX ENGINEの `/synthesis` をPOSTし、WAV bytesを得る。
- 入力: base URL、audio query、speaker id。
- 出力: WAV bytes。
- 主なエラー: 接続失敗、HTTPエラー、空レスポンス。
- 外部依存: VOICEVOX ENGINE、HTTP。
- テスト方針: `urlopen` をmonkeypatchし、POST先、JSON body、bytes返却、各種失敗を確認する。

### write_wav_bytes

`write_wav_bytes(path: Path, wav_bytes: bytes) -> None`

- 役割: WAV bytesをファイルに書き出す。親ディレクトリも作る。
- 入力: 出力パス、WAV bytes。
- 出力: なし。
- 主なエラー: 書き込み失敗。
- 外部依存: ファイルシステム。
- テスト方針: 書き込み、親ディレクトリ作成、書き込み失敗を確認する。

### synthesize_dialogue_wav

`synthesize_dialogue_wav(event: DialogueEvent, speaker_id: int, base_url: str, output_path: Path) -> DialogueEvent`

- 役割: 1つの `DialogueEvent` からWAVを生成し、`wav_path` と `duration_sec` を設定する。
- 入力: セリフイベント、speaker id、base URL、出力パス。
- 出力: 更新された同じ `DialogueEvent`。
- 主なエラー: `create_audio_query`、`synthesize_wav`、`write_wav_bytes`、`read_wav_info` の例外。
- 外部依存: VOICEVOX ENGINE、ファイルシステム。ただしテストでは差し替える。
- テスト方針: 依存関数をmonkeypatchし、呼び出し順、`voice_text` 使用、metadata設定、例外伝播を確認する。

### synthesize_dialogue_wavs

`synthesize_dialogue_wavs(events: list[ScriptEvent], speakers: list[dict], base_url: str, out_dir: Path, aliases: dict[str, str]) -> list[ScriptEvent]`

- 役割: イベント列の `DialogueEvent` だけをWAV化する。
- 入力: イベント列、話者一覧、base URL、個別WAV出力ディレクトリ、alias。
- 出力: 更新済みイベント列。
- 主なエラー: 話者解決失敗、セリフWAV生成失敗。
- 外部依存: `synthesize_dialogue_wav` 経由でVOICEVOX ENGINEとファイルシステム。
- テスト方針: `resolve_speaker_id` と `synthesize_dialogue_wav` をmonkeypatchし、順序、非セリフ保持、連番ファイル名、サニタイズ、例外伝播を確認する。

### attach_sound_effect_info

`attach_sound_effect_info(events: list[ScriptEvent]) -> list[ScriptEvent]`

- 役割: `SoundEffectEvent` のWAV長を取得して `duration_sec` に設定する。
- 入力: イベント列。
- 出力: 更新済みイベント列。
- 主なエラー: `read_wav_info` の例外。
- 外部依存: 効果音WAVファイル。
- テスト方針: `read_wav_info` をmonkeypatchし、path渡し、複数SE、非SE保持、順序、例外伝播を確認する。

### concatenate_wavs

`concatenate_wavs(events: list[ScriptEvent], output_path: Path) -> WavInfo`

- 役割: `DialogueEvent`、`SilenceEvent`、`SoundEffectEvent` を順番に連結して全体WAVを作る。
- 入力: イベント列、出力WAVパス。
- 出力: 出力WAVの `WavInfo`。
- 主なエラー: `DialogueEvent.wav_path` 未設定、音声WAVなし、WAV形式不一致、WAV読み込み・書き込み失敗。
- 外部依存: WAVファイル、ファイルシステム、`wave`。
- テスト方針: `tmp_path` と `wave` で小さいWAVを作り、順序、無音、効果音、親ディレクトリ作成、戻り値、形式不一致、未設定、音声なしを確認する。

### build_srt_cues

`build_srt_cues(events: list[ScriptEvent]) -> list[SrtCue]`

- 役割: イベント列の時間を積み上げ、`DialogueEvent` だけからSRTキューを作る。
- 入力: duration設定済みイベント列。
- 出力: `list[SrtCue]`。
- 主なエラー: `DialogueEvent.duration_sec` 未設定、`SoundEffectEvent.duration_sec` 未設定、空の `subtitle_text`。
- 外部依存: なし。
- テスト方針: 複数セリフ、無音・効果音の時刻反映、index、start/end、subtitle、各種未設定を確認する。

### format_srt_timestamp

`format_srt_timestamp(seconds: float) -> str`

- 役割: 秒数をSRT時刻形式 `HH:MM:SS,mmm` にする。
- 入力: 秒数。
- 出力: SRT時刻文字列。
- 主なエラー: 負数。
- 外部依存: なし。
- テスト方針: 0秒、ミリ秒、1時間超、負数を確認する。

### format_srt

`format_srt(cues: list[SrtCue]) -> str`

- 役割: `SrtCue` のリストをSRT本文文字列へ変換する。
- 入力: SRTキュー。
- 出力: SRT本文。
- 主なエラー: `end_sec < start_sec`、空text。
- 外部依存: なし。
- テスト方針: 複数cue、空行、末尾改行、不正時刻、空text、空cuesを確認する。

### write_srt_file

`write_srt_file(path: Path, cues: list[SrtCue]) -> None`

- 役割: SRT本文をUTF-8で書き出す。親ディレクトリも作る。
- 入力: 出力パス、SRTキュー。
- 出力: なし。
- 主なエラー: `format_srt` の例外、書き込み失敗。
- 外部依存: ファイルシステム。
- テスト方針: `tmp_path` で親ディレクトリ作成とUTF-8書き出しを確認する。

### generate_voicevox_assets

`generate_voicevox_assets(options: ScriptOptions) -> WavInfo`

- 役割: 台本読み込みから個別WAV、全体WAV、SRT生成までを統合する。
- 入力: `ScriptOptions`。
- 出力: 全体WAVの `WavInfo`。
- 主なエラー: 各工程の例外を伝播する。
- 外部依存: VOICEVOX ENGINE、ファイルシステム。
- テスト方針: 全依存関数をmonkeypatchし、処理順、主要引数、`DEFAULT_SPEAKER_ALIASES`、戻り値を確認する。

### parse_args

`parse_args(argv: list[str] | None = None) -> ScriptOptions`

- 役割: CLI引数を `ScriptOptions` に変換する。
- 入力: CLI引数リスト。`None` の場合は `sys.argv` 相当。
- 出力: `ScriptOptions`。
- 主なエラー: argparseによる引数エラー。
- 外部依存: 標準入力引数。
- テスト方針: 現時点では `main` 経由で指定値反映を確認している。既定値や必須引数不足は追加検討。

### main

`main(argv: list[str] | None = None) -> int`

- 役割: CLI入口。引数を解析し、`generate_voicevox_assets` を呼ぶ。
- 入力: CLI引数リスト。
- 出力: 終了コード。
- 主なエラー: `generate_voicevox_assets` の例外を捕捉し、`stderr` に `error: ...` を表示して `1` を返す。
- 外部依存: 標準出力、標準エラー、実行時はVOICEVOX ENGINEとファイルシステム。
- テスト方針: `generate_voicevox_assets` をmonkeypatchし、成功時の終了コードと表示、失敗時の終了コードとエラー表示を確認する。

---

## 5. 責務分離

- 台本解析は `parse_script` に閉じる。
- gap追加は `insert_gap_events` に閉じる。
- VOICEVOX HTTP呼び出しは `fetch_voicevox_speakers`、`create_audio_query`、`synthesize_wav` に閉じる。
- 話者解決は `resolve_speaker_id` に閉じる。
- 1セリフ合成は `synthesize_dialogue_wav` に閉じる。
- 複数セリフ合成は `synthesize_dialogue_wavs` に閉じる。
- WAV情報取得は `read_wav_info` に閉じる。
- 効果音長付与は `attach_sound_effect_info` に閉じる。
- WAV連結は `concatenate_wavs` に閉じる。
- SRTキュー生成は `build_srt_cues` に閉じる。
- SRT整形は `format_srt_timestamp` と `format_srt` に閉じる。
- SRT書き出しは `write_srt_file` に閉じる。
- 一式生成の順序制御は `generate_voicevox_assets` に閉じる。
- CLI固有の入出力は `parse_args` と `main` に閉じる。
