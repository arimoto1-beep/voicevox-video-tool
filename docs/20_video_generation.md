# 動画生成機能 仕様

## 1. 目的

この機能は、背景画像と音声ファイルから、ffmpegを使ってmp4動画を生成するための機能である。

第2章前半では、すでに生成済みの音声素材 `all.wav` と、1枚の背景画像 `background.png` を組み合わせて、動画ファイル `output.mp4` を作るところまでを対象とする。

最初の目標は以下である。

```txt
background.png
all.wav
  ↓
output.mp4
```

この段階では、字幕焼き込み、画像overlay、立ち絵、口パクなどは扱わない。まずは「静止画背景 + 音声」から確実にmp4を生成する。

---

## 2. 対象範囲

### 対象

今回の最初の実装対象は以下とする。

- 背景画像 + 音声からmp4を生成する
- `short` / `normal` layout を扱う
- ffmpegコマンドをPythonから実行する

### 対象外

今回の実装では以下を行わない。

- 字幕焼き込み
- ASS字幕生成
- overlay画像
- 立ち絵
- 口パク
- タイトル文字描画
- 背景画像の途中切り替え

これらは後続の拡張対象とし、第2章前半では実装しない。

---

## 3. 入力

動画生成では、以下の入力を扱う想定とする。

### audio_path

音声ファイルのパス。

第1章で生成した `all.wav` を想定する。

例:

```txt
tmp/cli_pipeline/all.wav
```

### background_path

背景画像のパス。

最初は1枚の静止画を動画全体の背景として使う。

例:

```txt
assets/background.png
```

### output_path

出力するmp4ファイルのパス。

例:

```txt
tmp/video/output.mp4
```

### layout

出力動画のサイズとfpsを決めるレイアウト名。

最初は以下の2種類を扱う。

- `short`
- `normal`

### ffmpeg_path

ffmpeg実行ファイルのパス、またはコマンド名。

既定値は `ffmpeg` を想定する。

---

## 4. 出力

出力はmp4動画ファイルとする。

例:

```txt
output.mp4
```

動画の内容は以下。

- 背景画像を動画全体に表示する
- 音声ファイルを動画の音声トラックとして入れる
- 音声の長さに合わせて動画を終了する

---

## 5. layout仕様

`layout` は、出力動画の幅、高さ、fpsを決める。

### short

YouTubeショートなどの縦長動画を想定する。

```txt
width: 1080
height: 1920
fps: 30
```

### normal

通常の横長動画を想定する。

```txt
width: 1920
height: 1080
fps: 30
```

不明なlayoutが指定された場合はエラーにする。

---

## 6. 背景画像の扱い

背景画像は、まず `cover` 方式で扱う。

`cover` は以下の意味である。

- 出力画面いっぱいに表示する
- アスペクト比は維持する
- はみ出した部分はcropする
- 余白は出さない

たとえば `short` layout の場合は、最終的に `1080x1920` の画面全体を背景画像で埋める。

ffmpeg filterとしては、以下の考え方になる。

```txt
scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1
```

将来的には、画像全体を必ず表示し、余白を許容する `contain` 方式を追加できる可能性がある。

ただし、第2章前半では `cover` のみを対象とする。

---

## 7. ffmpeg利用方針

ffmpegはPythonライブラリとして組み込むのではなく、外部コマンドとして呼び出す。

### Python側の責務

Python側は以下を担当する。

- 入力値の受け取り
- layoutの解決
- ffmpeg filterの組み立て
- ffmpegコマンドの組み立て
- ffmpeg実行

### ffmpeg側の責務

ffmpeg側は以下を担当する。

- 背景画像を動画化する
- 音声を結合する
- mp4として出力する

Python側では動画フレームを直接生成しない。動画化そのものはffmpegに任せる。

---

## 8. ffmpegコマンド例

`short` layout、`cover` 方式の場合のコマンド例。

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

各オプションの意味は以下。

- `-y`
  - 既存の出力ファイルを確認なしで上書きする。
- `-loop 1 -i background.png`
  - 背景画像を1枚の静止画としてループ入力する。
- `-i all.wav`
  - 音声ファイルを入力する。
- `-vf "..."`
  - 動画フィルタを指定する。
- `scale=1080:1920:force_original_aspect_ratio=increase`
  - アスペクト比を維持したまま、指定サイズを覆うまで拡大・縮小する。
- `crop=1080:1920`
  - 指定サイズからはみ出した部分を切り抜く。
- `setsar=1`
  - ピクセルのアスペクト比を1:1にする。
- `-r 30`
  - 出力fpsを30にする。
- `-c:v libx264`
  - 映像コーデックにH.264を使う。
- `-tune stillimage`
  - 静止画ベースの動画向けに調整する。
- `-c:a aac`
  - 音声コーデックにAACを使う。
- `-b:a 192k`
  - 音声ビットレートを192kbpsにする。
- `-pix_fmt yuv420p`
  - 再生互換性の高いピクセル形式にする。
- `-shortest`
  - 最も短い入力に合わせて出力を終了する。ここでは音声の長さに合わせて動画を終える目的で使う。
- `output.mp4`
  - 出力ファイル。

---

## 9. CLI案

第2章前半では、以下のようなCLIを想定する。

```powershell
python make_video.py ^
  --audio tmp/cli_pipeline/all.wav ^
  --background assets/background.png ^
  --output tmp/video/output.mp4 ^
  --layout short
```

引数は以下。

### --audio

入力音声ファイル。

例:

```txt
tmp/cli_pipeline/all.wav
```

### --background

背景画像ファイル。

例:

```txt
assets/background.png
```

### --output

出力mp4ファイル。

例:

```txt
tmp/video/output.mp4
```

### --layout

動画レイアウト。

指定可能な値:

- `short`
- `normal`

### --ffmpeg

ffmpegコマンドのパス。

省略時は `ffmpeg` を使う想定。

---

## 10. テスト方針

自動テストでは、実際のmp4生成までは行わない。

まずはPython側の責務をテスト対象にする。

### 自動テスト対象

- layout取得
- 背景filter生成
- ffmpegコマンド生成
- ffmpeg実行関数が `subprocess.run` を呼ぶこと

### 自動テストで避けること

- 実際にffmpegでmp4を生成すること
- ffmpegがインストールされていることを前提にすること
- 生成されたmp4の映像内容を検証すること

### 手動確認対象

実際の動画生成は手動確認とする。

手動確認では、ローカルにffmpegがインストールされている状態で、短い音声と背景画像から `output.mp4` が生成できることを確認する。

---

## 11. 今後の拡張予定

以下は今後の拡張として扱う。

- ASS字幕焼き込み
- overlay画像の重ね合わせ
- 立ち絵表示
- 話者ごとの立ち絵切り替え
- 簡易口パク
- 背景画像の途中切り替え
- `contain` 方式
- 詳細ログ
- dry-run

これらは第2章前半の対象には含めない。
