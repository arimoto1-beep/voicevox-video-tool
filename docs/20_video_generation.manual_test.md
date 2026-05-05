# 動画生成機能 手動確認手順

## 1. 目的

この手動確認では、`make_video.py` を実際に CLI から実行し、背景画像1枚と音声ファイル1つから ffmpeg を使って mp4 動画を生成できることを確認する。

確認対象は以下である。

```txt
background.png
all.wav
  ↓
output.mp4
```

自動テストでは ffmpeg を起動せず、Python 側の layout 解決、filter 生成、コマンド生成、実行関数呼び出しを確認している。  
この手動確認では、ローカル環境の ffmpeg を使って実際に mp4 が生成され、再生できることを確認する。

## 2. 前提条件

- ffmpeg がローカル環境にインストールされていること。
- Python が実行できること。
- `python make_video.py` が実行できること。
- 第1章で生成した `all.wav` が存在すること。
- 背景画像 `assets/background.png` が存在すること。
- まず `short` layout を確認し、その後 `normal` layout を確認すること。

確認に使う想定ファイル:

```txt
tmp/cli_pipeline/all.wav
assets/background.png
tmp/video/output_short.mp4
tmp/video/output_normal.mp4
```

`assets/background.png` が存在しない場合は、任意の PNG 画像を用意して配置する。

## 3. 事前確認

PowerShell で、repo root から実行する。

ffmpeg が使えることを確認する。

```powershell
ffmpeg -version
```

音声ファイルが存在することを確認する。

```powershell
dir tmp\cli_pipeline\all.wav
```

背景画像が存在することを確認する。

```powershell
dir assets\background.png
```

## 4. short layout の動画生成

`short` layout は 1080x1920, 30fps の縦長動画を生成する。

```powershell
python make_video.py `
  --audio tmp/cli_pipeline/all.wav `
  --background assets/background.png `
  --output tmp/video/output_short.mp4 `
  --layout short
```

成功時の想定出力:

```txt
video_path=tmp/video/output_short.mp4
```

## 5. normal layout の動画生成

`normal` layout は 1920x1080, 30fps の横長動画を生成する。

```powershell
python make_video.py `
  --audio tmp/cli_pipeline/all.wav `
  --background assets/background.png `
  --output tmp/video/output_normal.mp4 `
  --layout normal
```

成功時の想定出力:

```txt
video_path=tmp/video/output_normal.mp4
```

## 6. 生成されたmp4の確認観点

### short layout

- [ ] `tmp/video/output_short.mp4` が生成されていること。
- [ ] 動画が再生できること。
- [ ] 音声が再生されること。
- [ ] 動画の長さが音声の長さと大きくずれていないこと。
- [ ] 画面サイズが 1080x1920 であること。
- [ ] 背景画像が画面全体に表示されていること。
- [ ] 背景画像が cover 方式で表示されていること。
- [ ] 余白が出ていないこと。

### normal layout

- [ ] `tmp/video/output_normal.mp4` が生成されていること。
- [ ] 動画が再生できること。
- [ ] 音声が再生されること。
- [ ] 動画の長さが音声の長さと大きくずれていないこと。
- [ ] 画面サイズが 1920x1080 であること。
- [ ] 背景画像が画面全体に表示されていること。
- [ ] 背景画像が cover 方式で表示されていること。
- [ ] 余白が出ていないこと。

## 7. ffprobeで確認する場合

ffprobe が使える環境では、動画の解像度や fps をコマンドで確認できる。

short layout の映像 stream 確認:

```powershell
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 tmp/video/output_short.mp4
```

期待する主な値:

```txt
width=1080
height=1920
r_frame_rate=30/1
```

normal layout の映像 stream 確認:

```powershell
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 tmp/video/output_normal.mp4
```

期待する主な値:

```txt
width=1920
height=1080
r_frame_rate=30/1
```

動画ファイル全体の duration 確認:

```powershell
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 tmp/video/output_short.mp4
```

normal layout も同様に確認する場合:

```powershell
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 tmp/video/output_normal.mp4
```

必要に応じて、元の音声ファイルの duration も比較する。

```powershell
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 tmp/cli_pipeline/all.wav
```

## 8. 失敗時に見るポイント

### ffmpeg が見つからない場合

`ffmpeg -version` が失敗する場合は、ffmpeg がインストールされていないか、PATH が通っていない可能性がある。

確認すること:

- ffmpeg がインストールされているか。
- PowerShell から `ffmpeg` コマンドを実行できるか。
- 必要に応じて `--ffmpeg` に ffmpeg の実行ファイルパスを指定する。

例:

```powershell
python make_video.py `
  --audio tmp/cli_pipeline/all.wav `
  --background assets/background.png `
  --output tmp/video/output_short.mp4 `
  --layout short `
  --ffmpeg C:\tools\ffmpeg\bin\ffmpeg.exe
```

cmd.exe で実行する場合は、行継続文字として PowerShell のバッククォートではなく `^` を使う。

### all.wav が存在しない場合

`dir tmp\cli_pipeline\all.wav` が失敗する場合は、第1章の音声生成が完了していないか、出力先が異なる可能性がある。

確認すること:

- 第1章の CLI または手動確認で `all.wav` を生成済みか。
- `--audio` に指定しているパスが正しいか。

### assets/background.png が存在しない場合

`dir assets\background.png` が失敗する場合は、背景画像を用意していない可能性がある。

確認すること:

- `assets` ディレクトリが存在するか。
- `background.png` が配置されているか。
- 別の画像を使う場合、`--background` に正しいパスを指定しているか。

### 出力先ディレクトリを作成できない場合

`tmp/video/` を作成できない場合は、権限やパス指定に問題がある可能性がある。

確認すること:

- repo root から実行しているか。
- 出力先に書き込み権限があるか。
- `--output` に不正なパスを指定していないか。

### ffmpeg が非0終了する場合

CLI が `error: ...` を表示して終了する場合、ffmpeg が入力ファイルを読めない、codec 指定に失敗している、または出力先に書き込めない可能性がある。

確認すること:

- `all.wav` が壊れていないか。
- `background.png` が ffmpeg で読める画像か。
- 出力先ファイルを他のアプリで開いたままにしていないか。
- ffmpeg のエラーメッセージに入力ファイル名や codec に関する記述がないか。

### 背景画像の形式がffmpegで読めない場合

PNG の拡張子でも、ファイルが壊れている、特殊な形式で保存されている、または実体が PNG ではない場合に失敗することがある。

確認すること:

- 別の PNG 画像に差し替えて再実行する。
- 画像編集ソフトで標準的な PNG として書き出し直す。
- `--background` に指定しているファイルパスが正しいか。

## 9. 今回確認しないこと

この手動確認では、以下は確認しない。

- 字幕焼き込み
- ASS 字幕
- overlay 画像
- 立ち絵
- 口パク
- タイトル描画
- 背景画像の途中切り替え
- contain 方式

これらは第2章後半以降の拡張対象とする。

## 10. 記録しておく結果

手動確認後、以下を記録しておく。

- 実行したコマンド
- 生成されたファイルパス
- `short` layout の確認結果
- `normal` layout の確認結果
- ffprobe の結果
- 気づいた問題
- 次回に回すこと

記録例:

```txt
実行日:
環境:
ffmpeg version:

short:
command:
output_path:
再生:
音声:
解像度:
duration:
気づいたこと:

normal:
command:
output_path:
再生:
音声:
解像度:
duration:
気づいたこと:

次回に回すこと:
```
