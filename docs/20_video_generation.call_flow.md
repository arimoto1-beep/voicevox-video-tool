# 動画生成機能 呼び出し構成

## 1. 目的

このドキュメントは、第2章前半で実装する動画生成機能について、CLI実行時の呼び出し順と各関数の責務を整理する。

対象は、背景画像1枚と音声ファイル1つからmp4動画を生成する処理である。

```txt
background.png
all.wav
  ↓
output.mp4
```

この段階では、以下は扱わない。

- 字幕
- ASS字幕
- overlay画像
- 立ち絵
- 口パク
- タイトル描画
- 背景画像の途中切り替え

まずは、静止画背景と音声をffmpegに渡して、1本のmp4を作る呼び出し構成に限定する。

---

## 2. 全体の呼び出し構成

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

`main` はCLI入口、`generate_video` は動画生成の本体統合関数、`run_ffmpeg` は外部コマンド実行だけを担当する。

`build_cover_filter` は `build_ffmpeg_command` の内部で呼ぶ想定である。

---

## 3. CLIからの処理の流れ

想定CLI:

```powershell
python make_video.py ^
  --audio tmp/cli_pipeline/all.wav ^
  --background assets/background.png ^
  --output tmp/video/output.mp4 ^
  --layout short
```

処理の流れ:

1. `main(argv)` が呼ばれる。
2. `parse_args(argv)` がCLI引数を `VideoOptions` に変換する。
3. `main` が `generate_video(options)` を呼ぶ。
4. `generate_video` が `get_video_layout(options.layout)` でlayoutを解決する。
5. `generate_video` が `build_ffmpeg_command(options, layout)` でffmpegコマンドを作る。
6. `build_ffmpeg_command` が `build_cover_filter(layout)` で背景画像用filterを作る。
7. `generate_video` が `options.output_path.parent` を作成する。
8. `generate_video` が `run_ffmpeg(command)` を呼ぶ。
9. `run_ffmpeg` が `subprocess.run(command, check=True)` を呼ぶ。
10. 成功したら `main` が出力パスを表示し、終了コード `0` を返す。

成功時の表示案:

```txt
video_path=tmp/video/output.mp4
```

---

## 4. 各関数の役割

### main

CLIの入口。

責務:

- `parse_args` を呼ぶ
- `generate_video` を呼ぶ
- 成功時に結果を表示する
- 失敗時に `stderr` へ `error: ...` を表示する
- 終了コードを返す

`main` はffmpegコマンドの詳細を知らない。

### parse_args

CLI引数を `VideoOptions` に変換する。

受け取る引数:

- `--audio`
- `--background`
- `--output`
- `--layout`
- `--ffmpeg`

`--ffmpeg` は省略時に `ffmpeg` を使う。

`parse_args` は動画生成を実行しない。

### generate_video

動画生成全体の本体関数。

責務:

- layoutを解決する
- ffmpegコマンドを組み立てる
- 出力先の親ディレクトリを作る
- ffmpegを実行する

想定処理:

```python
layout = get_video_layout(options.layout)
command = build_ffmpeg_command(options, layout)
options.output_path.parent.mkdir(parents=True, exist_ok=True)
run_ffmpeg(command)
```

`generate_video` は例外を握りつぶさない。

### get_video_layout

layout名から、幅・高さ・fpsを返す。

対応layout:

- `short`: 1080x1920, 30fps
- `normal`: 1920x1080, 30fps

未知のlayoutは `ValueError` にする。

### build_ffmpeg_command

ffmpegに渡す `list[str]` のコマンドを作る。

責務:

- `ffmpeg_path` を先頭に入れる
- 背景画像を `-loop 1 -i background.png` として指定する
- 音声を `-i all.wav` として指定する
- `-vf` に背景filterを指定する
- fpsを `-r` に指定する
- 映像・音声コーデックを指定する
- `-shortest` を指定する
- 最後に `output_path` を指定する

この関数はコマンドを作るだけで、ffmpegは実行しない。

### build_cover_filter

背景画像をcover方式で表示するためのfilter文字列を作る。

`short` の例:

```txt
scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1
```

`normal` の例:

```txt
scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1
```

この段階では `cover` のみを扱う。

### run_ffmpeg

ffmpegコマンドを実行する。

想定:

```python
subprocess.run(command, check=True)
```

この関数はコマンドの意味を解釈しない。受け取った `command` を実行するだけにする。

### subprocess.run

実際に外部ffmpegを起動する標準ライブラリ関数。

自動テストではmonkeypatchで差し替え、実際のffmpegは起動しない。

---

## 5. エラー時の流れ

### 未知のlayout

```txt
main
  ↓
parse_args
  ↓
generate_video
  ↓
get_video_layout
  → ValueError
```

`ValueError` は `main` まで伝播し、`main` が以下のように表示して終了コード `1` を返す。

```txt
error: ...
```

### ffmpegが見つからない

```txt
run_ffmpeg
  ↓
subprocess.run
  → FileNotFoundError
```

`FileNotFoundError` は `main` まで伝播し、`error: ...` と表示する。

### ffmpeg実行失敗

```txt
run_ffmpeg
  ↓
subprocess.run(check=True)
  → subprocess.CalledProcessError
```

ffmpegが非0終了した場合は `subprocess.CalledProcessError` が発生する。

これも `main` で捕捉し、`error: ...` と表示して終了コード `1` を返す。

### 出力ディレクトリ作成失敗

```txt
generate_video
  ↓
options.output_path.parent.mkdir(...)
  → OSError
```

出力先の親ディレクトリを作れない場合も `main` まで伝播する。

---

## 6. 初期実装で扱わない分岐

第2章前半では、呼び出し構成に以下の分岐を入れない。

### 字幕焼き込み

ASS字幕生成や `subtitles` filter はまだ使わない。

### overlay画像

複数入力画像や `overlay` filter はまだ使わない。

### 立ち絵

話者ごとの立ち絵表示や切り替えはまだ扱わない。

### 口パク

音声解析や口パク用画像切り替えはまだ扱わない。

### タイトル描画

`drawtext` などでタイトル文字を描画する処理はまだ扱わない。

### 背景画像の途中切り替え

背景画像は動画全体で1枚だけ使う。

時間に応じた背景変更はまだ扱わない。

### contain方式

背景fit方式は `cover` のみ。

`contain` は後続拡張とする。

---

## 7. 今後の拡張余地

今後、ASS字幕やoverlayを追加する場合でも、現在の責務分離を維持する。

### ASS字幕焼き込み

追加する場合は、以下のような関数を増やす余地がある。

```txt
build_ass_filter
build_video_filter
```

`build_cover_filter` だけで完結していた `-vf` を、複数filterを合成する形に拡張する。

### overlay画像

overlay画像を扱う場合は、入力が増える。

```txt
-i background.png
-i overlay.png
-i all.wav
```

この場合、`build_ffmpeg_command` の入力指定とfilter組み立てを拡張する。

### 立ち絵表示

立ち絵を追加する場合もoverlayの一種として扱える。

話者ごとの切り替えを行う場合は、字幕やイベント列の時刻情報を参照する設計が必要になる。

### short / normal の追加拡張

現在は `short` と `normal` の2種類のみ。

将来、別サイズを追加する場合は `get_video_layout` のlayout定義を増やす。

### 背景fit方式

現在は `cover` のみ。

`contain` を追加する場合は、以下のようにfit方式を分ける。

```txt
build_cover_filter
build_contain_filter
```

または `build_background_filter(layout, fit)` のように統合する。

### dry-run

dry-runを追加する場合は、`run_ffmpeg` を呼ばず、生成したコマンドだけを表示する分岐を `main` または `generate_video` に追加する。

ただし、第2章前半では実装しない。
