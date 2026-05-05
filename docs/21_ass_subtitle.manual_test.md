# ASS字幕付き動画生成 手動確認手順

## 1. 目的

この手動確認では、`make_video.py` を実際にCLIから実行し、`--srt` に指定したSRT字幕ファイルからASS字幕ファイルが生成され、そのASS字幕がffmpegの `ass` filter によってmp4へ焼き込まれることを確認する。

確認対象は以下である。

```txt
background.png
all.wav
output.srt
  ↓
output.ass
  ↓
output_subtitled.mp4
```

具体的には、以下を確認する。

- SRTからASSファイルが生成されること。
- 生成されたASSがffmpegの `ass` filter に渡されること。
- 字幕付きmp4が生成されること。
- 字幕が動画に表示されること。
- `short` / `normal` で字幕の見え方を確認できること。

自動テストでは、SRTパース、ASS生成、ffmpegコマンド生成までは確認しているが、実際のffmpeg起動や動画内での字幕表示は確認していない。  
この手動確認では、ローカル環境のffmpegを使って、実際の字幕焼き込み結果を見る。

## 2. 前提条件

- `ffmpeg/bin/ffmpeg.exe` が配置されていること。
- `ffmpeg/bin/ffprobe.exe` が配置されていること。
- Python が実行できること。
- `python make_video.py` が実行できること。
- 第1章で生成した `tmp/cli_pipeline/all.wav` が存在すること。
- 第1章で生成した `tmp/cli_pipeline/output.srt` が存在すること。
- 背景画像を用意済みであること。
- まず `short` layout を確認し、その後 `normal` layout を確認すること。

確認に使う想定ファイル:

```txt
tmp/cli_pipeline/all.wav
tmp/cli_pipeline/output.srt
assets/background_short.png
assets/background_normal.png
tmp/video/output_short_subtitled.mp4
tmp/video/output_short_subtitled.ass
tmp/video/output_normal_subtitled.mp4
tmp/video/output_normal_subtitled.ass
```

## 3. 事前確認

PowerShellで、repo root から実行する。

ffmpeg が使えることを確認する。

```powershell
.\ffmpeg\bin\ffmpeg.exe -version
```

ffprobe が使えることを確認する。

```powershell
.\ffmpeg\bin\ffprobe.exe -version
```

音声ファイルが存在することを確認する。

```powershell
dir tmp\cli_pipeline\all.wav
```

SRTファイルが存在することを確認する。

```powershell
dir tmp\cli_pipeline\output.srt
```

背景画像が存在することを確認する。

```powershell
dir assets\background_short.png
dir assets\background_normal.png
```

## 4. short layout の字幕付き動画生成

`short` layout は 1080x1920, 30fps の縦長動画を生成する。  
`--srt` を指定すると、`output_path` の拡張子を `.ass` に置き換えたASSファイルが同じディレクトリに生成される。

```powershell
python make_video.py `
  --audio tmp/cli_pipeline/all.wav `
  --background assets/background_short.png `
  --srt tmp/cli_pipeline/output.srt `
  --output tmp/video/output_short_subtitled.mp4 `
  --layout short `
  --ffmpeg .\ffmpeg\bin\ffmpeg.exe
```

成功時の想定出力:

```txt
video_path=tmp/video/output_short_subtitled.mp4
```

同時に、以下のASSファイルが生成される想定である。

```txt
tmp/video/output_short_subtitled.ass
```

## 5. normal layout の字幕付き動画生成

`normal` layout は 1920x1080, 30fps の横長動画を生成する。

```powershell
python make_video.py `
  --audio tmp/cli_pipeline/all.wav `
  --background assets/background_normal.png `
  --srt tmp/cli_pipeline/output.srt `
  --output tmp/video/output_normal_subtitled.mp4 `
  --layout normal `
  --ffmpeg .\ffmpeg\bin\ffmpeg.exe
```

成功時の想定出力:

```txt
video_path=tmp/video/output_normal_subtitled.mp4
```

同時に、以下のASSファイルが生成される想定である。

```txt
tmp/video/output_normal_subtitled.ass
```

## 6. 生成されたASSファイルの確認

ASSファイルは、mp4の確認とは別に中身を確認する。ここで、SRTの内容がASSへ変換され、layout別の解像度やスタイルが反映されていることを見る。

PowerShellで中身を確認する例:

```powershell
Get-Content tmp\video\output_short_subtitled.ass -Encoding UTF8
Get-Content tmp\video\output_normal_subtitled.ass -Encoding UTF8
```

### short

- [ ] `tmp/video/output_short_subtitled.ass` が生成されていること。
- [ ] `[Script Info]` が含まれていること。
- [ ] `PlayResX: 1080` が含まれていること。
- [ ] `PlayResY: 1920` が含まれていること。
- [ ] `[V4+ Styles]` が含まれていること。
- [ ] `Style:` 行にshort用の文字サイズが反映されていること。
- [ ] short用の文字サイズとして `72` が含まれていること。
- [ ] short用の下余白として `140` が含まれていること。
- [ ] `[Events]` が含まれていること。
- [ ] `Dialogue:` 行が含まれていること。
- [ ] SRTの字幕本文が含まれていること。

### normal

- [ ] `tmp/video/output_normal_subtitled.ass` が生成されていること。
- [ ] `[Script Info]` が含まれていること。
- [ ] `PlayResX: 1920` が含まれていること。
- [ ] `PlayResY: 1080` が含まれていること。
- [ ] `[V4+ Styles]` が含まれていること。
- [ ] `Style:` 行にnormal用の文字サイズが反映されていること。
- [ ] normal用の文字サイズとして `56` が含まれていること。
- [ ] normal用の下余白として `80` が含まれていること。
- [ ] `[Events]` が含まれていること。
- [ ] `Dialogue:` 行が含まれていること。
- [ ] SRTの字幕本文が含まれていること。

## 7. 生成されたmp4の確認観点

mp4は、実際に動画プレイヤーで再生して確認する。字幕の見た目は自動テストでは判断できないため、ここで目視確認する。

### short layout

- [ ] `tmp/video/output_short_subtitled.mp4` が生成されていること。
- [ ] 動画が再生できること。
- [ ] 音声が再生されること。
- [ ] 字幕が表示されること。
- [ ] 字幕の表示タイミングが音声と大きくずれていないこと。
- [ ] 画面サイズが 1080x1920 であること。
- [ ] 字幕が読みやすい文字サイズであること。
- [ ] 字幕の縁取りが効いていること。
- [ ] 字幕が背景に埋もれていないこと。
- [ ] 字幕が下端に寄りすぎていないこと。
- [ ] 背景画像がcover方式で表示されていること。

### normal layout

- [ ] `tmp/video/output_normal_subtitled.mp4` が生成されていること。
- [ ] 動画が再生できること。
- [ ] 音声が再生されること。
- [ ] 字幕が表示されること。
- [ ] 字幕の表示タイミングが音声と大きくずれていないこと。
- [ ] 画面サイズが 1920x1080 であること。
- [ ] 字幕が読みやすい文字サイズであること。
- [ ] 字幕の縁取りが効いていること。
- [ ] 字幕が背景に埋もれていないこと。
- [ ] 字幕が下端に寄りすぎていないこと。
- [ ] 背景画像がcover方式で表示されていること。

## 8. ffprobeで確認する場合

ffprobe が使える環境では、動画の解像度やfpsをコマンドで確認できる。

short layout の映像stream確認:

```powershell
.\ffmpeg\bin\ffprobe.exe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 tmp/video/output_short_subtitled.mp4
```

期待する主な値:

```txt
width=1080
height=1920
r_frame_rate=30/1
```

normal layout の映像stream確認:

```powershell
.\ffmpeg\bin\ffprobe.exe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 tmp/video/output_normal_subtitled.mp4
```

期待する主な値:

```txt
width=1920
height=1080
r_frame_rate=30/1
```

duration確認:

```powershell
.\ffmpeg\bin\ffprobe.exe -v error -show_entries format=duration -of default=noprint_wrappers=1 tmp/video/output_short_subtitled.mp4
.\ffmpeg\bin\ffprobe.exe -v error -show_entries format=duration -of default=noprint_wrappers=1 tmp/video/output_normal_subtitled.mp4
```

元音声との比較:

```powershell
.\ffmpeg\bin\ffprobe.exe -v error -show_entries format=duration -of default=noprint_wrappers=1 tmp/cli_pipeline/all.wav
```

mp4のdurationが音声のdurationと大きくずれていないことを確認する。

## 9. 失敗時に見るポイント

### ffmpeg が見つからない場合

`.\ffmpeg\bin\ffmpeg.exe -version` が失敗する場合は、ffmpegの配置場所が想定と異なる可能性がある。

確認すること:

- `ffmpeg\bin\ffmpeg.exe` が存在するか。
- `--ffmpeg` に指定しているパスが正しいか。
- PowerShellのカレントディレクトリがrepo rootか。

### ffprobe が見つからない場合

`.\ffmpeg\bin\ffprobe.exe -version` が失敗する場合は、ffprobeが同梱されていない、または配置場所が異なる可能性がある。

確認すること:

- `ffmpeg\bin\ffprobe.exe` が存在するか。
- ffmpeg配布物にffprobeが含まれているか。

### all.wav が存在しない場合

`dir tmp\cli_pipeline\all.wav` が失敗する場合は、第1章の音声生成が完了していないか、出力先が異なる可能性がある。

確認すること:

- 第1章のCLIで `all.wav` を生成済みか。
- `--audio` のパスが正しいか。

### output.srt が存在しない場合

`dir tmp\cli_pipeline\output.srt` が失敗する場合は、第1章のSRT生成が完了していないか、出力先が異なる可能性がある。

確認すること:

- 第1章のCLIで `output.srt` を生成済みか。
- `--srt` のパスが正しいか。
- SRTファイルがUTF-8で読めるか。

### 背景画像が存在しない場合

背景画像の `dir` が失敗する場合は、画像を用意していないか、ファイル名が違う可能性がある。

確認すること:

- `assets/background_short.png` が存在するか。
- `assets/background_normal.png` が存在するか。
- `--background` のパスが正しいか。

### ASSファイルが生成されない場合

`--srt` を指定しているのに `.ass` が生成されない場合は、SRTの読み込みやパースで失敗している可能性がある。

確認すること:

- `--srt` を指定しているか。
- SRTの時刻行が `00:00:00,000 --> 00:00:01,500` の形式になっているか。
- CLIが `error: ...` を表示していないか。
- 出力先ディレクトリに書き込み権限があるか。

### ffmpeg がASSファイルを読み込めない場合

ffmpegのエラーにASSファイル名や `ass` filter が出ている場合、ASSファイルのパスや内容に問題がある可能性がある。

確認すること:

- `.ass` ファイルが存在するか。
- `.ass` ファイルを `Get-Content -Encoding UTF8` で読めるか。
- `[Script Info]`, `[V4+ Styles]`, `[Events]` が含まれているか。

### ASS filter のパス指定で失敗する場合

Windows環境では、ffmpeg filter内のパス指定で失敗する可能性がある。特に、ドライブレターの `:`, バックスラッシュ、空白、シングルクォートを含むパスには注意する。

初期実装では単純な相対パスを優先して確認する。

確認すること:

- まず `tmp/video/output_short_subtitled.ass` のような単純な相対パスで試す。
- パスに空白や特殊文字が含まれていないか。
- repo root から実行しているか。

### 字幕が文字化けする場合

確認すること:

- SRTファイルがUTF-8で保存されているか。
- 生成されたASSファイルがUTF-8で読めるか。
- ffmpegが使用するフォントで日本語が表示できるか。
- `Arial` で日本語がうまく出ない場合は、今後フォント指定の調整が必要になる。

### 字幕が表示されない場合

確認すること:

- `.ass` の `[Events]` に `Dialogue:` 行があるか。
- `Dialogue:` 行の時刻が動画duration内に収まっているか。
- `--srt` を指定して実行したか。
- ffmpegのログに `ass` filter のエラーが出ていないか。

### 字幕の位置やサイズが見づらい場合

初期値は仮設定であるため、手動確認で調整が必要になる可能性がある。

確認すること:

- `short` の文字サイズが大きすぎないか、小さすぎないか。
- `normal` の文字サイズが大きすぎないか、小さすぎないか。
- 下余白が足りているか。
- 縁取りが背景に対して十分か。

### ffmpeg が非0終了する場合

CLIが `error: ...` を表示して終了する場合、ffmpegが非0終了している可能性がある。

確認すること:

- ffmpegのエラーメッセージ。
- 入力ファイルの存在。
- 背景画像の形式。
- 音声ファイルの形式。
- ASS filterのパス。
- 出力先ファイルを他のアプリで開いたままにしていないか。

## 10. 今回確認しないこと

この手動確認では、以下は確認しない。

- 話者ごとの字幕色分け
- 立ち絵表示
- 話者ごとの立ち絵切り替え
- 口パク
- 字幕アニメーション
- overlay画像
- contain方式
- YouTubeへのアップロード
- noteへの動画埋め込み

## 11. 記録しておく結果

手動確認後、以下を記録しておく。

- 実行したコマンド
- 生成されたASSファイルパス
- 生成されたmp4ファイルパス
- `short` layout の確認結果
- `normal` layout の確認結果
- ffprobe の結果
- 字幕の見た目
- 字幕タイミングの感想
- 気づいた問題
- 次回に回すこと

記録例:

```txt
実行日:
環境:
ffmpeg version:
ffprobe version:

short:
command:
ass_path:
mp4_path:
ASS中身:
再生:
音声:
字幕表示:
字幕タイミング:
字幕サイズ:
字幕位置:
縁取り:
解像度:
duration:
気づいたこと:

normal:
command:
ass_path:
mp4_path:
ASS中身:
再生:
音声:
字幕表示:
字幕タイミング:
字幕サイズ:
字幕位置:
縁取り:
解像度:
duration:
気づいたこと:

次回に回すこと:
```
