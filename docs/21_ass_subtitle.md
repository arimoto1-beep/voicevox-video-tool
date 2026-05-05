# ASS字幕対応 機能仕様

## 1. 目的

ASS字幕対応の目的は、既存の字幕キューまたはSRT相当の字幕情報から、動画焼き込みに適したASS字幕ファイルを生成し、ffmpegで字幕付きmp4を作れるようにすることである。

現在はSRT字幕を生成できるが、SRTは字幕の見た目を細かく制御する用途には向いていない。動画に直接焼き込む字幕では、文字サイズ、縁取り、表示位置、余白などを安定して指定したい。

ASSを使いたい主な理由は以下である。

- 文字サイズを指定しやすい。
- 縁取りを指定しやすい。
- 表示位置を調整しやすい。
- `short` / `normal` layout で字幕スタイルを変えやすい。
- 背景に埋もれにくい字幕を作りやすい。
- 将来的に話者ごとのスタイル分けにつなげやすい。

初期段階では、背景画像 + 音声 + ASS字幕から、字幕付きmp4を生成できるところを目指す。

## 2. 現在の字幕生成状況

現在は、第1章の音声・字幕素材生成処理としてSRT字幕を生成している。

既存のSRT処理は削除しない。SRTは今後も以下の用途で残す。

- 確認用
- 互換用
- 他ツール連携用
- デバッグ用

今後の整理としては、同じ字幕キューからSRTとASSの両方を出力できる構造が望ましい。

## 3. ASS字幕で実現したいこと

初期段階で実現したいことは以下である。

- 字幕テキストを表示する。
- 字幕の開始時刻・終了時刻を反映する。
- `short` / `normal` に応じて文字サイズ・余白を変える。
- 字幕に縁取りをつける。
- 背景に埋もれにくい字幕にする。
- ffmpegで焼き込めるASSファイルを生成する。

初期段階では、以下は対象外とする。

- 話者ごとの色分け
- 立ち絵連動
- 口パク連動
- 字幕のアニメーション
- ルビ
- 複雑な字幕レイアウト
- 複数行の高度な制御

## 4. 入力

ASS字幕生成に必要な入力候補は以下である。

### 字幕キュー

既存の `SrtCue` 相当の情報を使う想定である。

- `start_sec`
- `end_sec`
- `text`

既存のSRT出力と同じ字幕キューを使えると、SRTとASSの内容差分を小さくできる。

### SRT相当の字幕情報

実装影響を抑える場合は、既存のSRTファイルまたはSRT相当の字幕情報からASSを生成する案も考えられる。

ただし、SRT本文から再パースする方式は、時刻やテキストの扱いが遠回りになる。可能であれば、内部の字幕キューを入力にするほうがよい。

### layout

動画の出力layoutに応じて字幕スタイルを変える。

- `short`
- `normal`

### 字幕スタイル設定

初期実装で扱う候補は以下である。

- `font_name`
- `font_size`
- `margin_v`
- `outline`
- `shadow`
- `alignment`

最初は固定値でもよいが、将来的に設定ファイルやCLI引数から変更できる余地を残す。

## 5. 出力

出力はASS字幕ファイルとする。

例:

```txt
output.ass
```

将来的には、用途に応じて以下のような出力先も考えられる。

```txt
tmp/video/output.ass
tmp/cli_pipeline/output.ass
```

ASSファイルは、ffmpegの `ass` filter に渡して動画へ焼き込む。

## 6. ASSファイルの基本構造

ASSファイルは、最低限以下のセクションを持つ想定にする。

```txt
[Script Info]
[V4+ Styles]
[Events]
```

### [Script Info]

字幕ファイル全体の基本情報を記述する。

初期実装では、必要最小限の項目にとどめる。

例:

```txt
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
```

`PlayResX` / `PlayResY` は layout に応じて設定する。

### [V4+ Styles]

字幕スタイルを定義する。

初期実装では、複雑な機能は使わず、1つの標準スタイルで字幕を出す方針にする。

例:

```txt
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Yu Gothic UI,96,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,5,1,2,60,60,260,1
```

### [Events]

字幕の表示タイミングと本文を記述する。

例:

```txt
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,こんにちは
```

## 7. 時刻形式

SRTとASSでは時刻形式が異なるため、秒数からASS時刻文字列へ変換する処理が必要になる。

SRTの例:

```txt
00:00:01,230
```

ASSの例:

```txt
0:00:01.23
```

ASSでは centisecond 単位を使う想定にする。秒数からASS時刻文字列へ変換する関数が必要になる。

想定する変換例:

```txt
0.0      -> 0:00:00.00
1.23     -> 0:00:01.23
61.5     -> 0:01:01.50
3661.234 -> 1:01:01.23
```

丸め方は実装時に明確にする。SRT側のミリ秒丸めとずれすぎないように注意する。

## 8. short / normal の字幕スタイル

`short` / `normal` で字幕スタイルを分ける方針にする。

初期値:

第40回の手動確認で、`short` / `normal` ともに字幕サイズが小さく、字幕位置が下すぎる課題があった。また、日本語表示はできたが `Arial` から Yu Gothic UI 系フォントへ自動フォールバックしていたため、日本語表示を前提に `font_name` を `Yu Gothic UI` にする。

縁取りは十分だったため、`outline` は据え置く。`shadow` と `alignment` も現状維持する。

### short

縦長のYouTubeショート向け。スマートフォン画面で読みやすいように、文字を大きめにし、下端に近すぎない位置に置く。

仮設定:

```txt
font_name: Yu Gothic UI
font_size: 96
margin_v: 260
alignment: 下中央
outline: 5
shadow: 1
```

### normal

横長動画向け。画面幅が広いため、`short` より少し小さめの文字サイズにする。

仮設定:

```txt
font_name: Yu Gothic UI
font_size: 72
margin_v: 150
alignment: 下中央
outline: 4
shadow: 1
```

ASSの `alignment` は下中央を表す `2` を使う想定にする。

具体的な数値は初期値であり、手動確認を通じて調整する。

## 9. ffmpegでの焼き込み方針

ASS字幕をffmpegで焼き込む場合は、既存の背景filterに `ass` filter を追加する形になる可能性が高い。

概念的なコマンド例:

```powershell
ffmpeg -y `
  -loop 1 -i background.png `
  -i all.wav `
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,ass=output.ass" `
  -r 30 `
  -c:v libx264 `
  -tune stillimage `
  -c:a aac `
  -b:a 192k `
  -pix_fmt yuv420p `
  -shortest `
  output.mp4
```

`make_video.py` では、既存の `build_cover_filter` の結果にASS filterを連結する形が考えられる。

例:

```txt
scale=...,crop=...,setsar=1,ass=output.ass
```

Windows環境では、ASSファイルパスのエスケープやクォートに注意が必要である。特に、空白、バックスラッシュ、ドライブレター、コロンを含むパスをffmpeg filter内へ渡す場合は、通常のコマンド引数とは別のエスケープ規則を考える必要がある。

初期実装では、まず相対パスや単純なパスで動作確認する方針が現実的である。

## 10. SRT処理との関係

SRT処理は削除しない。

役割の整理:

- SRT: 確認用・互換用
- ASS: 動画焼き込み用

SRTは、人間が内容を確認しやすく、他ツールとも連携しやすい。一方で、ASSは動画に焼き込む字幕の見た目を制御しやすい。

望ましい構造は、同じ字幕キューからSRTとASSの両方を生成する形である。

```txt
字幕キュー
  ├─ output.srt
  └─ output.ass
```

この構造にすると、字幕本文や表示タイミングの差分を抑えやすい。

## 11. 実装方針の候補

ASS生成の責務をどこに置くかは、以下の2案が考えられる。

### 案A: make_voicevox_assets.py にASS生成を追加する

第1章の音声・字幕素材生成の一部として、SRTに加えてASSも出力する案である。

イメージ:

```txt
台本
  ↓
all.wav
output.srt
output.ass
```

メリット:

- 音声・字幕素材生成の段階で `output.ass` まで揃う。
- SRTとASSを同じ字幕キューから生成しやすい。
- 動画生成側は `output.ass` を受け取るだけでよい。
- 字幕本文とタイミングの生成責務を第1章側に集約できる。

デメリット:

- 第1章の既存実装に手を入れる必要がある。
- 既存テストへの影響が出る可能性がある。
- 動画用layoutの情報を素材生成側に持ち込む必要があるかもしれない。
- `make_voicevox_assets.py` が動画表示スタイルまで知ることになり、責務が少し広がる。

### 案B: make_video.py にASS生成を追加する

動画生成時にASSを作る案である。

イメージ:

```txt
all.wav
output.srt
background.png
  ↓
make_video.py
  ↓
一時的または指定先の output.ass
  ↓
字幕付きmp4
```

メリット:

- 動画layoutに応じた字幕スタイルを扱いやすい。
- 動画生成側で `short` / `normal` に応じたASSを作れる。
- 第1章の音声素材生成処理をあまり触らずに済む。
- ffmpeg焼き込みとASS filterの都合を同じ場所で扱いやすい。

デメリット:

- SRTや字幕キューを動画生成側へ渡す必要がある。
- `make_video.py` の責務が増える。
- 将来的に字幕生成責務が分散する可能性がある。
- SRT本文を再パースする方式にすると、字幕キューから直接生成するより遠回りになる。

### 現時点での推奨方針

現時点では、以下の方針を推奨する。

- SRT生成は既存のまま残す。
- 初期実装では、字幕キューからASSを生成する関数を追加するのが理想。
- ただし、実装の影響範囲を抑えるため、まずは既存のSRTまたは字幕情報からASSを作る小さな関数として始める。
- 動画焼き込みは `make_video.py` 側で、既存の背景filterにASS filterを追加する形にする。
- 設計が固まったら、SRT/ASSを同じ字幕キューから出力する構造に整理する。

短期的には案B寄りで始めると、動画layoutに応じた字幕スタイルを扱いやすい。  
ただし、中期的には同じ字幕キューからSRTとASSを出す構造へ寄せるのがよい。

## 12. テスト方針

ASS対応の自動テストでは、実際にffmpegで字幕焼き込み動画を生成するところまでは行わない。

まずは以下をテスト対象にする。

- 秒数からASS時刻文字列への変換
- ASSファイル本文の生成
- `short` / `normal` の字幕スタイル取得
- ASS filterを含むffmpegコマンド生成
- SRT処理が壊れていないこと

自動テストでは、ffmpeg本体や動画再生環境には依存しない。

手動確認では、実際にASS字幕を焼き込んだmp4を生成して確認する。

手動確認で見る観点:

- 字幕が表示されること。
- 字幕の時刻が音声と大きくずれていないこと。
- `short` layoutで読みやすいサイズ・位置になっていること。
- `normal` layoutで読みやすいサイズ・位置になっていること。
- 背景に字幕が埋もれていないこと。
- Windows環境でASSファイルパスをffmpegへ渡せること。

## 13. 今回まだやらないこと

ASS字幕対応の初期設計では、以下は対象外とする。

- 立ち絵表示
- 話者ごとの立ち絵切り替え
- 口パク
- 字幕アニメーション
- 話者ごとの色分け
- 複雑な字幕装飾
- YouTubeへの自動アップロード
- noteへの動画埋め込み

## 14. 今後の拡張予定

今後の拡張として、以下を検討する。

- 話者ごとの字幕スタイル
- 立ち絵の表示切り替え
- 口パクとの連動
- 字幕位置のlayout別調整
- セーフエリア対応
- 画像overlayとの組み合わせ
- noteやYouTubeでの見え方確認

ASS字幕は、これらの拡張の土台になる。初期段階では、字幕本文、時刻、layout別スタイル、ffmpeg焼き込みに絞って実装を進める。
