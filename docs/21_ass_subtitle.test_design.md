# ASS字幕対応 テスト設計

## 1. テスト目的

ASS字幕対応の初期実装について、SRTファイルからASS字幕を生成し、ffmpegコマンドの `ass` filter に接続できることを確認する。

自動テストでは実際のffmpegは起動しない。mp4への字幕焼き込み結果は、次回以降の手動確認で扱う。

## 2. 対象ファイル

- `make_video.py`
- `tests/test_make_video.py`

## 3. テスト方針

- 既存のSRT生成処理は変更しない。
- SRTは確認用・互換用として残す。
- ASSは動画焼き込み用として追加する。
- `--srt` がある場合だけASS生成とASS filter連結を行う。
- `--srt` がない場合は従来どおり字幕なし動画のコマンドになることを確認する。
- 実際のffmpegは起動しない。
- ファイルI/Oは `tmp_path` を使い、外部ファイルに依存しない。

## 4. テスト観点一覧

| 観点ID | 対象 | 確認内容 | 対応するテスト | 備考 |
| --- | --- | --- | --- | --- |
| ASS-STYLE-001 | `get_ass_subtitle_style` | `short` layout用スタイルが期待値になること | `test_get_ass_subtitle_style_returns_short_style` | font_size 72, margin_v 140 |
| ASS-STYLE-002 | `get_ass_subtitle_style` | `normal` layout用スタイルが期待値になること | `test_get_ass_subtitle_style_returns_normal_style` | font_size 56, margin_v 80 |
| ASS-TIME-001 | `format_ass_time` | 秒数をASS時刻形式へ変換できること | `test_format_ass_time_formats_seconds` | `H:MM:SS.CS` |
| ASS-TIME-002 | `format_ass_time` | 負数で `ValueError` になること | `test_format_ass_time_raises_for_negative_seconds` | 不正時刻を拒否 |
| ASS-TEXT-001 | `escape_ass_text` | 改行が `\N` になること | `test_escape_ass_text_escapes_newline_and_braces` | ASSの複数行表現 |
| ASS-TEXT-002 | `escape_ass_text` | `{` と `}` がエスケープされること | `test_escape_ass_text_escapes_newline_and_braces` | override tag誤認防止 |
| ASS-SRT-001 | `parse_srt_time` | SRT時刻を秒数へ変換できること | `test_parse_srt_time_converts_timestamp_to_seconds` | 1時間超えも確認 |
| ASS-SRT-002 | `parse_srt_time` | 不正形式で `ValueError` になること | `test_parse_srt_time_raises_for_invalid_format` | `HH:MM:SS,mmm` 以外 |
| ASS-SRT-003 | `parse_srt_file` | 一般的なSRTから `SubtitleCue` を作れること | `test_parse_srt_file_reads_cues` | 空行区切り |
| ASS-SRT-004 | `parse_srt_file` | 複数行字幕を `\n` で保持できること | `test_parse_srt_file_keeps_multiline_text` | ASS生成時に `\N` へ変換 |
| ASS-SRT-005 | `parse_srt_file` | 不正ブロックで `ValueError` になること | `test_parse_srt_file_raises_for_invalid_block` | timing行なし |
| ASS-CONTENT-001 | `build_ass_content` | ASS基本セクションを含むこと | `test_build_ass_content_builds_ass_sections_and_dialogues` | `[Script Info]`, `[V4+ Styles]`, `[Events]` |
| ASS-CONTENT-002 | `build_ass_content` | `PlayResX` / `PlayResY` がlayoutに従うこと | `test_build_ass_content_builds_ass_sections_and_dialogues` | shortで1080x1920 |
| ASS-CONTENT-003 | `build_ass_content` | Style行にstyle値が反映されること | `test_build_ass_content_builds_ass_sections_and_dialogues` | font_size, margin_v, outline, shadow |
| ASS-CONTENT-004 | `build_ass_content` | Dialogue行にASS時刻と字幕本文が入ること | `test_build_ass_content_builds_ass_sections_and_dialogues` | 改行は `\N` |
| ASS-WRITE-001 | `write_ass_file` | 親ディレクトリを作成してASSを書き出すこと | `test_write_ass_file_creates_parent_and_writes_utf8` | `tmp_path` 使用 |
| ASS-WRITE-002 | `write_ass_file` | UTF-8で読み戻せること | `test_write_ass_file_creates_parent_and_writes_utf8` | 日本語本文 |
| ASS-PATH-001 | `escape_path_for_ffmpeg_filter` | バックスラッシュが `/` になること | `test_escape_path_for_ffmpeg_filter_escapes_windows_path` | Windowsパス対策 |
| ASS-PATH-002 | `escape_path_for_ffmpeg_filter` | コロンとシングルクォートがエスケープされること | `test_escape_path_for_ffmpeg_filter_escapes_windows_path` | filter内パス用 |
| ASS-FILTER-001 | `build_ass_filter` | `ass=...` 形式になること | `test_build_ass_filter_returns_ass_filter` | ffmpeg ASS filter |
| ASS-FILTER-002 | `build_video_filter` | `ass_path=None` ではcover filterだけになること | `test_build_video_filter_returns_cover_filter_without_ass` | 既存挙動維持 |
| ASS-FILTER-003 | `build_video_filter` | `ass_path` ありではcover filterとASS filterが連結されること | `test_build_video_filter_appends_ass_filter` | `,ass=...` |
| ASS-CMD-001 | `build_ffmpeg_command` | `ass_path` なしでは既存と同じfilterになること | `test_build_ffmpeg_command_builds_expected_arguments` | 字幕なし経路 |
| ASS-CMD-002 | `build_ffmpeg_command` | `ass_path` ありでは `-vf` にASS filterを含むこと | `test_build_ffmpeg_command_uses_ass_video_filter_when_ass_path_is_given` | 字幕あり経路 |
| ASS-ARGS-001 | `parse_args` | `--srt` 省略時に `None` になること | `test_parse_args_builds_video_options_with_defaults` | 既存CLI互換 |
| ASS-ARGS-002 | `parse_args` | `--srt` 指定時に `VideoOptions.srt_path` に入ること | `test_parse_args_accepts_srt_path` | 任意引数 |
| ASS-GEN-001 | `generate_video` | `srt_path` ありでASSを書き出すこと | `test_generate_video_with_srt_writes_ass_and_runs_ffmpeg` | output_pathの拡張子を`.ass`へ |
| ASS-GEN-002 | `generate_video` | `srt_path` ありでASS filter付きコマンドを実行関数へ渡すこと | `test_generate_video_with_srt_writes_ass_and_runs_ffmpeg` | ffmpeg本体は起動しない |
| ASS-GEN-003 | `generate_video` | `srt_path` なしでASSを書き出さないこと | `test_generate_video_without_srt_does_not_write_ass` | 字幕なし経路 |
| ASS-GEN-004 | `generate_video` | `srt_path` なしで従来どおりcover filterだけになること | `test_generate_video_without_srt_does_not_write_ass` | 既存挙動維持 |

## 5. 自動テストで確認すること

- ASS字幕スタイル取得
- ASS時刻形式への変換
- ASS本文用テキストエスケープ
- SRT時刻のパース
- SRTファイルから字幕キューへの変換
- ASS本文生成
- ASSファイル書き出し
- ffmpeg filter内パスの最低限のエスケープ
- ASS filter生成
- `-vf` へのASS filter連結
- `--srt` のCLI引数パース
- `srt_path` あり・なしの `generate_video` 分岐

## 6. 自動テストで確認しないこと

- 実際にffmpegで字幕付きmp4を生成すること
- 生成されたmp4に字幕が見えること
- 字幕の見た目が読みやすいこと
- Windowsのあらゆるパス形式でASS filterが動くこと
- ffmpegの `ass` filter が利用可能であること
- フォントがローカル環境に存在すること
- 話者ごとの字幕色分け
- 立ち絵表示
- 口パク
- overlay画像
- contain方式
- dry-run
- 詳細ログ

## 7. 手動確認で見ること

次回の手動確認では、実際にffmpegを起動して以下を見る。

- `--srt` 指定で `.ass` ファイルが生成されること
- 字幕付きmp4が生成されること
- 字幕が画面に表示されること
- 字幕のタイミングが音声と大きくずれないこと
- `short` layoutで字幕サイズと位置が読みやすいこと
- `normal` layoutで字幕サイズと位置が読みやすいこと
- 背景に字幕が埋もれないこと
- `--srt` なしでは字幕なしmp4を生成できること

## 8. 今後追加する観点

- `main` で `--srt` 指定時の成功・失敗表示を確認する
- `parse_srt_file` で空ファイルや空字幕をどう扱うか確認する
- `build_ass_content` で空字幕キューをどう扱うか確認する
- Windowsの絶対パス、空白を含むパスのffmpeg実動作確認
- `subprocess.CalledProcessError` の表示確認
- ASS字幕の手動見た目調整
- 話者ごとの字幕スタイル
- セーフエリア対応
- 複数行字幕の見え方
