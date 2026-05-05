# 動画生成機能 関数設計

## 1. 前提

本ドキュメントは `docs/20_video_generation.md` をもとに、第2章前半で実装する動画生成機能を関数単位に分解した設計メモである。

対象は、背景画像1枚と音声ファイル1つから、ffmpegを使ってmp4動画を生成するところまでとする。

```txt
background.png
all.wav
  ↓
output.mp4
```

この段階では、以下は実装しない。

- 字幕焼き込み
- ASS字幕生成
- overlay画像
- 立ち絵
- 口パク
- タイトル文字描画
- 背景画像の途中切り替え

---

## 2. 設計方針

### 2.1 Python側の責務

Python側では、以下だけを行う。

- 入力値を受け取る
- layoutを解決する
- 背景画像用のffmpeg filterを組み立てる
- ffmpegコマンドを組み立てる
- `subprocess.run` でffmpegを実行する

動画フレームの生成やエンコード処理はPython側では行わない。

### 2.2 ffmpeg側の責務

ffmpeg側では、以下を行う。

- 背景画像を動画化する
- 音声を結合する
- mp4として出力する

### 2.3 テスト方針

自動テストでは、実際のmp4生成は行わない。

テスト対象は、layout解決、filter生成、コマンド生成、`subprocess.run` 呼び出しまでとする。

実際にffmpegでmp4を生成する確認は、手動確認スクリプトで行う。

---

## 3. データ構造

### VideoLayout

layout名に対応する出力動画の形式。

想定するdataclass:

```python
@dataclass(frozen=True)
class VideoLayout:
    name: str
    width: int
    height: int
    fps: int
```

初期実装で扱うlayout:

```txt
short:
  width: 1080
  height: 1920
  fps: 30

normal:
  width: 1920
  height: 1080
  fps: 30
```

### VideoOptions

動画生成に必要な入力値。

想定するdataclass:

```python
@dataclass
class VideoOptions:
    audio_path: Path
    background_path: Path
    output_path: Path
    layout: str = "short"
    ffmpeg_path: str = "ffmpeg"
```

### FfmpegCommand

コマンドは特別なクラスにせず、まずは `list[str]` として扱う。

理由:

- `subprocess.run` にそのまま渡せる
- shell依存のクォートを避けやすい
- 自動テストで引数単位の比較がしやすい

---

## 4. 関数一覧

第2章前半では、少なくとも以下の関数を想定する。

- `get_video_layout`
- `build_cover_filter`
- `build_ffmpeg_command`
- `run_ffmpeg`
- `generate_video`
- `parse_args`
- `main`

必要に応じて、入力ファイル確認や出力ディレクトリ作成の補助関数を追加してもよい。

---

## 5. 関数仕様

### get_video_layout

#### シグネチャ案

```python
def get_video_layout(name: str) -> VideoLayout:
    ...
```

#### 役割

layout名から、動画の幅・高さ・fpsを取得する。

#### 入力

- `name`: layout名
  - `short`
  - `normal`

#### 出力

- `VideoLayout`

#### 主なエラー

- 未知のlayout名が指定された場合は `ValueError`

#### 外部依存

なし。

#### テスト方針

- `short` が `1080x1920, 30fps` になること
- `normal` が `1920x1080, 30fps` になること
- 未知のlayoutで `ValueError` になること

---

### build_cover_filter

#### シグネチャ案

```python
def build_cover_filter(layout: VideoLayout) -> str:
    ...
```

#### 役割

背景画像をcover方式で画面いっぱいに表示するためのffmpeg filter文字列を作る。

#### 入力

- `layout`: `VideoLayout`

#### 出力

- ffmpegの `-vf` に渡すfilter文字列

#### 出力例

`short` の場合:

```txt
scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1
```

`normal` の場合:

```txt
scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1
```

#### 主なエラー

- 基本的にはなし。
- `VideoLayout` の値が不正な場合は、呼び出し元で検証済みとする。

#### 外部依存

なし。

#### テスト方針

- `short` 用filterが期待文字列になること
- `normal` 用filterが期待文字列になること

---

### build_ffmpeg_command

#### シグネチャ案

```python
def build_ffmpeg_command(options: VideoOptions, layout: VideoLayout) -> list[str]:
    ...
```

#### 役割

ffmpegに渡すコマンド引数を組み立てる。

#### 入力

- `options`: `VideoOptions`
- `layout`: 解決済みの `VideoLayout`

#### 出力

- `subprocess.run` に渡す `list[str]`

#### コマンド構成

`short` layoutの場合、概念的には以下と同じ内容を組み立てる。

```powershell
ffmpeg -y ^
  -loop 1 -i background.png ^
  -i all.wav ^
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1" ^
  -r 30 ^
  -c:v libx264 ^
  -tune stillimage ^
  -c:a aac ^
  -b:a 192k ^
  -pix_fmt yuv420p ^
  -shortest ^
  output.mp4
```

`list[str]` としては以下のような形を想定する。

```python
[
    "ffmpeg",
    "-y",
    "-loop", "1",
    "-i", "background.png",
    "-i", "all.wav",
    "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
    "-r", "30",
    "-c:v", "libx264",
    "-tune", "stillimage",
    "-c:a", "aac",
    "-b:a", "192k",
    "-pix_fmt", "yuv420p",
    "-shortest",
    "output.mp4",
]
```

#### 主なエラー

- 基本的にはなし。
- 入力ファイルの存在確認をこの関数で行うかは、実装時に分けてもよい。

#### 外部依存

なし。

#### テスト方針

- `ffmpeg_path` が先頭に入ること
- `background_path` が画像入力として入ること
- `audio_path` が音声入力として入ること
- `build_cover_filter` の結果が `-vf` に入ること
- `layout.fps` が `-r` に入ること
- `output_path` が最後に入ること

---

### run_ffmpeg

#### シグネチャ案

```python
def run_ffmpeg(command: list[str]) -> None:
    ...
```

#### 役割

ffmpegコマンドを実行する。

#### 入力

- `command`: ffmpegコマンドの引数リスト

#### 出力

- なし

#### 処理概要

`subprocess.run` を使ってffmpegを実行する。

想定:

```python
subprocess.run(command, check=True)
```

#### 主なエラー

- ffmpegコマンドが見つからない場合は `FileNotFoundError`
- ffmpegが失敗した場合は `subprocess.CalledProcessError`

これらは握りつぶさず、上位へ伝播する。

#### 外部依存

- ffmpeg
- `subprocess`

#### テスト方針

- `subprocess.run` をmonkeypatchし、期待した `command` と `check=True` で呼ばれることを確認する
- 実際のffmpegは実行しない

---

### generate_video

#### シグネチャ案

```python
def generate_video(options: VideoOptions) -> None:
    ...
```

#### 役割

動画生成全体の本体関数。

#### 入力

- `options`: `VideoOptions`

#### 出力

- なし

#### 処理順

1. `get_video_layout(options.layout)`
2. `build_ffmpeg_command(options, layout)`
3. `options.output_path.parent.mkdir(parents=True, exist_ok=True)`
4. `run_ffmpeg(command)`

#### 主なエラー

- 未知のlayout
- 出力ディレクトリ作成失敗
- ffmpeg未インストール
- ffmpeg実行失敗

#### 外部依存

- ファイルシステム
- ffmpeg

#### テスト方針

- `get_video_layout` / `build_ffmpeg_command` / `run_ffmpeg` をmonkeypatchし、呼び出し順と主要引数を確認する
- 出力ディレクトリが作られることを確認する
- ffmpeg実行失敗時に例外が伝播することを確認する

---

### parse_args

#### シグネチャ案

```python
def parse_args(argv: list[str] | None = None) -> VideoOptions:
    ...
```

#### 役割

CLI引数を `VideoOptions` に変換する。

#### 入力

- `argv`: CLI引数。`None` の場合は `sys.argv` 相当。

#### 出力

- `VideoOptions`

#### 引数

必須:

- `--audio`
- `--background`
- `--output`
- `--layout`

任意:

- `--ffmpeg`
  - 既定値: `ffmpeg`

#### 主なエラー

- 必須引数が不足した場合はargparseのエラー
- 不正なlayout名は `generate_video` 側、またはargparseのchoicesで検出する

#### 外部依存

- CLI引数

#### テスト方針

- 必須引数から `VideoOptions` を作れること
- `--ffmpeg` 省略時に `ffmpeg` が使われること
- `--ffmpeg` 指定時に値が反映されること

---

### main

#### シグネチャ案

```python
def main(argv: list[str] | None = None) -> int:
    ...
```

#### 役割

CLIの入口。

#### 入力

- `argv`: CLI引数

#### 出力

- 終了コード

#### 処理概要

1. `parse_args(argv)` で `VideoOptions` を作る。
2. `generate_video(options)` を呼ぶ。
3. 成功時は出力パスを表示し、`0` を返す。
4. 失敗時は `stderr` に `error: ...` を表示し、`1` を返す。

#### 成功時の表示案

```txt
video_path=tmp/video/output.mp4
```

#### 主なエラー

- `generate_video` からの例外を捕捉する

#### 外部依存

- 標準出力
- 標準エラー
- 実行時はffmpeg

#### テスト方針

- `generate_video` をmonkeypatchし、成功時に終了コード0になること
- 成功時に `video_path=...` を表示すること
- 失敗時に終了コード1になること
- 失敗時に `stderr` へ `error: ...` を表示すること

---

## 6. 呼び出し構成

想定する呼び出し順は以下。

```txt
main
  ↓
parse_args
  ↓
generate_video
  ↓
get_video_layout
  ↓
build_ffmpeg_command
  ↓
build_cover_filter
  ↓
run_ffmpeg
  ↓
subprocess.run
```

`build_cover_filter` は `build_ffmpeg_command` の内部で呼ぶ想定。

---

## 7. エラー方針

第2章前半では、エラーを細かく独自型に分けすぎない。

まずは以下の方針にする。

- 未知のlayoutは `ValueError`
- ffmpeg未インストールは `FileNotFoundError` を上位へ伝播
- ffmpeg実行失敗は `subprocess.CalledProcessError` を上位へ伝播
- CLIの `main` では例外を捕捉し、`error: ...` と表示して終了コード1にする

入力ファイルの存在確認をPython側で行うか、ffmpegのエラーに任せるかは実装時に決める。

ただし、自動テストではffmpeg本体に依存しないことを優先する。

---

## 8. 初期実装でやらないこと

以下は本関数設計の対象外とする。

- ASS字幕焼き込み
- ASS字幕生成
- overlay画像の重ね合わせ
- 立ち絵表示
- 話者ごとの立ち絵切り替え
- 簡易口パク
- 背景画像の途中切り替え
- `contain` 方式
- 詳細ログ
- dry-run

これらを見越して、layout解決、filter生成、コマンド生成、実行を分けておく。
