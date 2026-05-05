# ASS字幕対応 関数設計

## 1. 前提

ASS字幕対応は、既存のSRT生成処理を削除せず、動画焼き込み用の字幕形式を追加するための機能である。

初期実装では、`make_video.py` 側で `--srt` を受け取り、SRTファイルからASSファイルを生成する。生成したASSは、ffmpegの `ass` filter に渡してmp4へ焼き込む。

`--srt` が指定されない場合は、従来どおり背景画像 + 音声のみのmp4を生成する。

## 2. 追加するデータ構造

### AssSubtitleStyle

ASS字幕スタイルを表す。

```python
@dataclass(frozen=True)
class AssSubtitleStyle:
    font_name: str
    font_size: int
    margin_v: int
    outline: int
    shadow: int
    alignment: int = 2
```

`alignment=2` は下中央を表す想定である。

### SubtitleCue

SRTから読み取った字幕キューを表す。

```python
@dataclass(frozen=True)
class SubtitleCue:
    start_sec: float
    end_sec: float
    text: str
```

### VideoOptions

既存の動画生成オプションに `srt_path` とASS字幕スタイルの一時上書き値を追加する。

```python
@dataclass
class VideoOptions:
    audio_path: Path
    background_path: Path
    output_path: Path
    layout: str = "short"
    ffmpeg_path: str = "ffmpeg"
    srt_path: Path | None = None
    ass_font_size: int | None = None
    ass_margin_v: int | None = None
```

## 3. 追加・変更する関数一覧

- `get_ass_subtitle_style`
- `apply_ass_style_overrides`
- `format_ass_time`
- `escape_ass_text`
- `parse_srt_time`
- `parse_srt_file`
- `build_ass_content`
- `write_ass_file`
- `escape_path_for_ffmpeg_filter`
- `build_ass_filter`
- `build_video_filter`
- `build_ffmpeg_command`
- `generate_video`
- `parse_args`

## 4. 各関数の設計

### get_ass_subtitle_style

```python
def get_ass_subtitle_style(layout: VideoLayout) -> AssSubtitleStyle:
    ...
```

役割:

- layoutに応じたASS字幕スタイルを返す。
- 第40回の手動確認で字幕サイズが小さく、字幕位置が下すぎたため、初期値として文字サイズと下余白を大きくする。
- 日本語表示を前提に `font_name` は `Yu Gothic UI` にする。
- 縁取りは十分だったため、`outline` は据え置く。

入力:

- `layout`: `VideoLayout`

出力:

- `AssSubtitleStyle`
- `short`: `font_name="Yu Gothic UI"`, `font_size=96`, `margin_v=260`, `outline=5`, `shadow=1`, `alignment=2`
- `normal`: `font_name="Yu Gothic UI"`, `font_size=72`, `margin_v=150`, `outline=4`, `shadow=1`, `alignment=2`

主なエラー:

- 未知の `layout.name` の場合は `ValueError`

外部依存:

- なし

テスト方針:

- `short` / `normal` のスタイル値を確認する。

### apply_ass_style_overrides

```python
def apply_ass_style_overrides(
    style: AssSubtitleStyle,
    font_size: int | None = None,
    margin_v: int | None = None,
) -> AssSubtitleStyle:
    ...
```

役割:

- layout別デフォルトのASS字幕スタイルに、CLI引数で指定された一時上書き値を適用する。
- 元の `style` は変更せず、新しい `AssSubtitleStyle` を返す。

仕様:

- `font_size` が指定された場合は `style.font_size` を上書きする。
- `margin_v` が指定された場合は `style.margin_v` を上書きする。
- 未指定の値は元の `style` の値を使う。
- `font_name`, `outline`, `shadow`, `alignment` は元の `style` から引き継ぐ。
- `font_size <= 0` は `ValueError` にする。
- `margin_v < 0` は `ValueError` にする。

テスト方針:

- 未指定時に元のstyleと同じ値になること。
- `font_size` / `margin_v` を個別に上書きできること。
- 両方を同時に上書きできること。
- 元のstyleが変更されないこと。
- 不正値で `ValueError` になること。

### format_ass_time

```python
def format_ass_time(seconds: float) -> str:
    ...
```

役割:

- 秒数をASS時刻形式 `H:MM:SS.CS` に変換する。

入力:

- `seconds`: 秒数

出力:

- ASS時刻文字列

主なエラー:

- 負数の場合は `ValueError`

外部依存:

- なし

テスト方針:

- 0秒、秒とcentisecond、分をまたぐ値、1時間を超える値、負数を確認する。

### escape_ass_text

```python
def escape_ass_text(text: str) -> str:
    ...
```

役割:

- ASSのDialogue本文として扱うため、最低限のエスケープを行う。

入力:

- `text`: 字幕本文

出力:

- エスケープ済み本文

仕様:

- 改行 `\n` を `\N` にする。
- `{` を `\{` にする。
- `}` を `\}` にする。

外部依存:

- なし

テスト方針:

- 改行と波括弧の変換を確認する。

### parse_srt_time

```python
def parse_srt_time(value: str) -> float:
    ...
```

役割:

- SRT時刻文字列 `HH:MM:SS,mmm` を秒数へ変換する。

入力:

- SRT時刻文字列

出力:

- 秒数

主なエラー:

- 不正形式の場合は `ValueError`

外部依存:

- なし

テスト方針:

- 通常の時刻、1時間超え、不正形式を確認する。

### parse_srt_file

```python
def parse_srt_file(path: Path) -> list[SubtitleCue]:
    ...
```

役割:

- UTF-8のSRTファイルを読み取り、`SubtitleCue` のリストへ変換する。

入力:

- `path`: SRTファイルパス

出力:

- `list[SubtitleCue]`

主なエラー:

- ファイル読み込み失敗
- 不正なSRTブロック
- 不正な時刻形式
- 終了時刻が開始時刻より前

外部依存:

- ファイルシステム

テスト方針:

- 一般的なSRT、複数行字幕、不正ブロックを確認する。

### build_ass_content

```python
def build_ass_content(
    cues: list[SubtitleCue],
    layout: VideoLayout,
    style: AssSubtitleStyle,
) -> str:
    ...
```

役割:

- ASSファイル本文を生成する。

入力:

- `cues`: 字幕キュー
- `layout`: 動画layout
- `style`: ASS字幕スタイル

出力:

- ASS本文文字列

仕様:

- `[Script Info]`
- `[V4+ Styles]`
- `[Events]`

を含める。

主なエラー:

- 現時点では明示的な独自エラーは設けない。
- 時刻変換時に負数があれば `ValueError` が伝播する。

外部依存:

- なし

テスト方針:

- セクション、PlayRes、Style行、Dialogue行を確認する。

### write_ass_file

```python
def write_ass_file(path: Path, content: str) -> None:
    ...
```

役割:

- ASS本文をUTF-8でファイルへ書き出す。

入力:

- `path`: 出力先
- `content`: ASS本文

出力:

- なし

主なエラー:

- ディレクトリ作成失敗
- ファイル書き込み失敗

外部依存:

- ファイルシステム

テスト方針:

- 親ディレクトリ作成とUTF-8読み戻しを確認する。

### escape_path_for_ffmpeg_filter

```python
def escape_path_for_ffmpeg_filter(path: Path) -> str:
    ...
```

役割:

- ffmpeg filter内で使うパスを最低限エスケープする。

仕様:

- `\` を `/` に変換する。
- `:` を `\:` に変換する。
- `'` を `\'` に変換する。

外部依存:

- なし

テスト方針:

- Windows風パスの変換を確認する。

### build_ass_filter

```python
def build_ass_filter(ass_path: Path) -> str:
    ...
```

役割:

- ffmpegのASS filter文字列を生成する。

出力例:

```txt
ass=tmp/video/output.ass
```

外部依存:

- なし

テスト方針:

- `ass=...` 形式になることを確認する。

### build_video_filter

```python
def build_video_filter(layout: VideoLayout, ass_path: Path | None = None) -> str:
    ...
```

役割:

- ffmpegの `-vf` に渡す動画filter文字列を生成する。

仕様:

- `ass_path` が `None` の場合は従来どおりcover filterのみ。
- `ass_path` がある場合は、cover filterの後ろにASS filterを連結する。

外部依存:

- なし

テスト方針:

- 字幕なし、字幕ありのfilter文字列を確認する。

### build_ffmpeg_command

```python
def build_ffmpeg_command(
    options: VideoOptions,
    layout: VideoLayout,
    ass_path: Path | None = None,
) -> list[str]:
    ...
```

役割:

- ffmpegへ渡す `list[str]` のコマンドを組み立てる。

変更点:

- `build_cover_filter` ではなく `build_video_filter` を使う。
- `ass_path` がある場合、`-vf` にASS filterを含める。

外部依存:

- なし

テスト方針:

- 既存の字幕なしコマンドが壊れていないこと。
- 字幕ありで `-vf` にASS filterが含まれること。

### generate_video

```python
def generate_video(options: VideoOptions) -> None:
    ...
```

役割:

- 動画生成全体の本体関数。

処理順:

1. `get_video_layout(options.layout)`
2. `options.output_path.parent.mkdir(parents=True, exist_ok=True)`
3. `options.srt_path` がある場合はSRTを読みASSを書き出す。
4. `options.srt_path` がある場合はlayout別デフォルトスタイルに `ass_font_size` / `ass_margin_v` の上書きを適用する。
5. `build_ffmpeg_command(options, layout, ass_path=ass_path)`
6. `run_ffmpeg(command)`

外部依存:

- ファイルシステム
- ffmpeg

テスト方針:

- `srt_path` ありでASSを書き出し、ASS filter付きコマンドを実行関数へ渡すこと。
- `srt_path` ありで `ass_font_size` / `ass_margin_v` を指定した場合、生成ASSのStyle行に反映されること。
- `srt_path` なしでASSを書き出さず、従来どおりのfilterになること。

### parse_args

```python
def parse_args(argv: list[str] | None = None) -> VideoOptions:
    ...
```

役割:

- CLI引数を `VideoOptions` に変換する。

変更点:

- 任意引数 `--srt` を追加する。
- 任意引数 `--ass-font-size` を追加する。
- 任意引数 `--ass-margin-v` を追加する。

テスト方針:

- `--srt` 指定時に `VideoOptions.srt_path` に入ること。
- `--ass-font-size` 指定時に `VideoOptions.ass_font_size` に入ること。
- `--ass-margin-v` 指定時に `VideoOptions.ass_margin_v` に入ること。
- 省略時に `None` になること。

## 5. 初期実装でやらないこと

- `make_voicevox_assets.py` 側へのASS生成追加
- `--ass` によるASS直接指定
- 話者ごとの字幕色分け
- 立ち絵表示
- 話者ごとの立ち絵切り替え
- 口パク
- 字幕アニメーション
- 複雑な複数行制御
- ルビ
- YouTubeへの自動アップロード
- noteへの動画埋め込み
- overlay画像
- contain方式
- dry-run
- 詳細ログ
