# 動画生成機能 テスト設計

## 1. 目的

このドキュメントは、第2章前半で追加した動画生成機能について、`tests/test_make_video.py` が確認している内容を人間がレビューしやすい形で整理するためのテスト観点表である。

対象は、背景画像1枚と音声ファイル1つから ffmpeg で mp4 を生成する初期実装である。

```txt
background.png
all.wav
  ↓
output.mp4
```

この段階では、実際の mp4 生成結果そのものではなく、Python 側の責務である layout 解決、背景 filter 生成、ffmpeg コマンド生成、実行関数呼び出し、CLI 入出力を確認する。

## 2. 対象ファイル

- `make_video.py`
- `tests/test_make_video.py`

## 3. テスト方針

- 実際の ffmpeg は起動しない。
- mp4 生成そのものは自動テストしない。
- layout 解決、filter 生成、コマンド生成、実行関数呼び出しを確認する。
- `subprocess.run` や `run_ffmpeg` は monkeypatch で差し替え、外部環境に依存しないテストにする。
- ffmpeg がインストールされていること、入力ファイルが実在することは前提にしない。
- 実際の動画生成は、別途手動確認で扱う。

## 4. テスト観点一覧

| 観点ID | 対象 | 確認内容 | 対応するテスト | 備考 |
| --- | --- | --- | --- | --- |
| VG-LAYOUT-001 | `get_video_layout` | `short` layout が 1080x1920, 30fps になること | `test_get_video_layout_returns_short_layout` | YouTube Shorts 向け縦長 layout |
| VG-LAYOUT-002 | `get_video_layout` | `normal` layout が 1920x1080, 30fps になること | `test_get_video_layout_returns_normal_layout` | 通常の横長 layout |
| VG-LAYOUT-003 | `get_video_layout` | 未知の layout 名で `ValueError` になること | `test_get_video_layout_raises_for_unknown_layout` | 不正 layout を早めに検出する |
| VG-FILTER-001 | `build_cover_filter` | `short` 用 cover filter が期待文字列になること | `test_build_cover_filter_returns_short_filter` | `scale=1080:1920...crop=1080:1920,setsar=1` |
| VG-FILTER-002 | `build_cover_filter` | `normal` 用 cover filter が期待文字列になること | `test_build_cover_filter_returns_normal_filter` | `scale=1920:1080...crop=1920:1080,setsar=1` |
| VG-CMD-001 | `build_ffmpeg_command` | `ffmpeg_path` がコマンド先頭に入ること | `test_build_ffmpeg_command_builds_expected_arguments` | `custom-ffmpeg` を指定して確認 |
| VG-CMD-002 | `build_ffmpeg_command` | `-y` が含まれること | `test_build_ffmpeg_command_builds_expected_arguments` | 既存出力を確認なしで上書きする指定 |
| VG-CMD-003 | `build_ffmpeg_command` | 背景画像が `-loop 1 -i background.png` として入ること | `test_build_ffmpeg_command_builds_expected_arguments` | 静止画をループ入力にする |
| VG-CMD-004 | `build_ffmpeg_command` | 音声ファイルが `-i all.wav` として入ること | `test_build_ffmpeg_command_builds_expected_arguments` | 第1章で生成した `all.wav` を想定 |
| VG-CMD-005 | `build_ffmpeg_command` | `-vf` の直後に cover filter が入ること | `test_build_ffmpeg_command_builds_expected_arguments` | 背景画像の cover 表示を ffmpeg filter で指定 |
| VG-CMD-006 | `build_ffmpeg_command` | `-r` の直後に layout の fps が入ること | `test_build_ffmpeg_command_builds_expected_arguments` | 初期実装では 30fps |
| VG-CMD-007 | `build_ffmpeg_command` | `libx264`, `aac`, `192k`, `yuv420p`, `-shortest` が含まれること | `test_build_ffmpeg_command_builds_expected_arguments` | mp4 出力の基本 codec と音声長に合わせる指定 |
| VG-CMD-008 | `build_ffmpeg_command` | `output_path` が最後に入ること | `test_build_ffmpeg_command_builds_expected_arguments` | ffmpeg の出力先指定 |
| VG-RUN-001 | `run_ffmpeg` | `subprocess.run` が `command` と `check=True` で呼ばれること | `test_run_ffmpeg_calls_subprocess_run` | monkeypatch により実際の ffmpeg は起動しない |
| VG-RUN-002 | `run_ffmpeg` | 実際の ffmpeg は起動しないこと | `test_run_ffmpeg_calls_subprocess_run` | `subprocess.run` を差し替えて確認 |
| VG-GEN-001 | `generate_video` | layout 解決、コマンド生成、出力ディレクトリ作成、ffmpeg 実行の流れになること | `test_generate_video_creates_output_parent_and_runs_ffmpeg` | 実行結果のコマンド末尾に `output_path` が入ることを確認 |
| VG-GEN-002 | `generate_video` | 出力ディレクトリが作成されること | `test_generate_video_creates_output_parent_and_runs_ffmpeg` | `tmp_path / "nested" / "output.mp4"` で確認 |
| VG-GEN-003 | `generate_video` | `run_ffmpeg` が呼ばれること | `test_generate_video_creates_output_parent_and_runs_ffmpeg` | `run_ffmpeg` を monkeypatch して確認 |
| VG-GEN-004 | `generate_video` | 例外を握りつぶさないこと | `test_generate_video_does_not_swallow_unknown_layout` | 現行テストでは未知 layout の `ValueError` 伝播を確認 |
| VG-GEN-005 | `generate_video` | `run_ffmpeg` の例外が握りつぶされないこと | 未実装 | 今後追加検討したい観点 |
| VG-ARGS-001 | `parse_args` | 必須引数から `VideoOptions` を作れること | `test_parse_args_builds_video_options_with_defaults` | `--audio`, `--background`, `--output` |
| VG-ARGS-002 | `parse_args` | `--layout` 省略時に `short` になること | `test_parse_args_builds_video_options_with_defaults` | CLI 既定値 |
| VG-ARGS-003 | `parse_args` | `--layout normal` 指定時に `normal` になること | `test_parse_args_accepts_normal_layout_and_custom_ffmpeg` | 横長 layout 指定 |
| VG-ARGS-004 | `parse_args` | `--ffmpeg` 省略時に `ffmpeg` になること | `test_parse_args_builds_video_options_with_defaults` | PATH 上の ffmpeg を使う想定 |
| VG-ARGS-005 | `parse_args` | `--ffmpeg` 指定時に値が反映されること | `test_parse_args_accepts_normal_layout_and_custom_ffmpeg` | 任意の ffmpeg 実行ファイルパスを指定できる |
| VG-MAIN-001 | `main` | 成功時に終了コード 0 になること | `test_main_returns_zero_and_prints_video_path` | `generate_video` は monkeypatch |
| VG-MAIN-002 | `main` | 成功時に `video_path=...` が標準出力に出ること | `test_main_returns_zero_and_prints_video_path` | 記事や手動確認に貼りやすい出力 |
| VG-MAIN-003 | `main` | 失敗時に終了コード 1 になること | `test_main_returns_one_and_prints_error` | `generate_video` から例外を発生させて確認 |
| VG-MAIN-004 | `main` | 失敗時に `error: ...` が標準エラーに出ること | `test_main_returns_one_and_prints_error` | CLI 利用時の短いエラー表示 |

## 5. 自動テストで確認しないこと

現行の自動テストでは、以下は確認しない。

- 実際に mp4 が生成されること
- 生成された mp4 の映像内容
- 生成された mp4 の音声内容
- ffmpeg がインストールされていること
- 背景画像ファイルや音声ファイルが実在すること
- `run_ffmpeg` で発生した `FileNotFoundError` や `subprocess.CalledProcessError` が `generate_video` から伝播すること
- 字幕焼き込み
- ASS 字幕生成
- overlay 画像
- 立ち絵
- 口パク
- タイトル描画

## 6. 手動確認で見ること

実際の動画生成は、ffmpeg がインストールされたローカル環境で手動確認する。

- CLI を実行できること
- `background.png` と `all.wav` から `output.mp4` が生成されること
- 動画の長さが音声に合っていること
- `short` layout が 1080x1920 で出力されること
- `normal` layout が 1920x1080 で出力されること
- 背景画像が cover 方式で表示されること
- 音声が再生されること

想定する CLI 例:

```powershell
python make_video.py ^
  --audio tmp/cli_pipeline/all.wav ^
  --background assets/background.png ^
  --output tmp/video/output.mp4 ^
  --layout short
```

## 7. 今後追加するテスト観点

第2章後半以降で機能を拡張する場合は、以下の観点を追加する。

- `run_ffmpeg` の例外が `generate_video` で握りつぶされないこと
- `main` が `FileNotFoundError` や `subprocess.CalledProcessError` を `error: ...` として表示すること
- ASS 字幕焼き込み
- ASS 字幕生成
- overlay 画像
- 立ち絵表示
- 話者ごとの立ち絵切り替え
- 簡易口パク
- contain 方式
- dry-run
- 詳細ログ

これらは第2章前半の初期実装範囲には含めない。現時点では、背景画像1枚と音声ファイル1つから mp4 を生成するための Python 側の最小責務だけをテスト対象とする。
