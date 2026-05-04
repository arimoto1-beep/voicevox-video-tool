# 音声・字幕生成機能 テスト設計

## 1. 実装済みテスト観点

| 対象 | 観点 | テスト名 | 状態 |
|---|---|---|---|
| read_script_file | 存在する台本ファイルを読み込める | `test_read_script_file_reads_existing_file` | 実装済み |
| read_script_file | 存在しないファイルで `FileNotFoundError` になる | `test_read_script_file_missing_file_raises_file_not_found` | 実装済み |
| read_script_file | 空行やコメント行も読み込み段階ではそのまま保持する | `test_read_script_file_keeps_blank_and_comment_lines` | 実装済み |
| parse_script | 全角コロンの話者つきセリフを `DialogueEvent` にできる | `test_parse_script_parses_full_width_colon_dialogue` | 実装済み |
| parse_script | 半角コロンの話者指定を扱える | `test_parse_script_parses_half_width_colon_dialogue` | 実装済み |
| parse_script | 話者省略時に直前話者を引き継げる | `test_parse_script_inherits_previous_speaker` | 実装済み |
| parse_script | 直前話者がない話者省略行は `ScriptParseError` になる | `test_parse_script_omitted_speaker_without_previous_speaker_raises` | 実装済み |
| parse_script | `||` で `voice_text` と `subtitle_text` を分離できる | `test_parse_script_splits_voice_text_and_subtitle_text` | 実装済み |
| parse_script | `(間 0.25)` を `SilenceEvent(source="script")` にできる | `test_parse_script_parses_silence_event` | 実装済み |
| parse_script | 間の秒数が負数の場合に `ScriptParseError` になる | `test_parse_script_negative_silence_duration_raises` | 実装済み（追加検討から移動） |
| parse_script | `(SE se\pop.wav)` を `SoundEffectEvent` にできる | `test_parse_script_parses_sound_effect_event` | 実装済み |
| parse_script | コメント行と空行を無視できる | `test_parse_script_ignores_blank_and_comment_lines` | 実装済み |
| parse_script | セリフ用個別パラメータを解析できる | `test_parse_script_parses_dialogue_params` | 実装済み |
| parse_script | 個別パラメータが `key=value` 形式でない場合に `ScriptParseError` になる | `test_parse_script_invalid_param_format_raises` | 実装済み（追加検討から移動） |
| parse_script | 効果音用個別パラメータを解析できる | `test_parse_script_parses_sound_effect_params` | 実装済み |
| parse_script | 未対応のセリフ用パラメータは `ScriptParseError` になる | `test_parse_script_unsupported_dialogue_param_raises` | 実装済み |
| parse_script | 未対応の効果音用パラメータは `ScriptParseError` になる | `test_parse_script_unsupported_sound_effect_param_raises` | 実装済み |
| parse_script | セリフ本文が空の場合に `ScriptParseError` になる | `test_parse_script_empty_dialogue_text_raises` | 実装済み（追加検討から移動） |
| parse_script | `voice_text` が空の場合に `ScriptParseError` になる | `test_parse_script_empty_voice_text_raises` | 実装済み（追加検討から移動） |
| parse_script | `subtitle_text` が空の場合に `ScriptParseError` になる | `test_parse_script_empty_subtitle_text_raises` | 実装済み（追加検討から移動） |
| insert_gap_events | 連続する `DialogueEvent` 同士の間に `SilenceEvent(source="gap")` を挿入する | `test_insert_gap_events_inserts_gap_between_consecutive_dialogues` | 実装済み |
| insert_gap_events | `DialogueEvent` と `SilenceEvent` の間にはgapを入れない | `test_insert_gap_events_does_not_insert_between_dialogue_and_silence` | 実装済み |
| insert_gap_events | `DialogueEvent` と `SoundEffectEvent` の間にはgapを入れない | `test_insert_gap_events_does_not_insert_between_dialogue_and_sound_effect` | 実装済み |
| insert_gap_events | `gap_sec` が0ならイベント列の内容が変わらない | `test_insert_gap_events_zero_gap_keeps_event_list_content` | 実装済み |
| insert_gap_events | 空のイベント列に対して空リストを返す | `test_insert_gap_events_empty_list_returns_empty_list` | 実装済み（追加検討から移動） |
| insert_gap_events | イベントが1件だけの場合にgapを挿入しない | `test_insert_gap_events_single_event_does_not_insert_gap` | 実装済み（追加検討から移動） |
| insert_gap_events | `gap_sec` が負数なら `ValueError` になる | `test_insert_gap_events_negative_gap_raises` | 実装済み |
| read_wav_info | 正常なWAVファイルから `channels` / `sample_width` / `frame_rate` / `frame_count` / `duration_sec` を取得できる | `test_read_wav_info_reads_wav_format_info` | 実装済み |
| read_wav_info | 存在しないファイルで `FileNotFoundError` になる | `test_read_wav_info_missing_file_raises_file_not_found` | 実装済み |
| read_wav_info | WAVではないファイルで `ValueError` になる | `test_read_wav_info_non_wav_file_raises_value_error` | 実装済み |
| read_wav_info | `duration_sec` が `frame_count / frame_rate` で計算される | `test_read_wav_info_duration_is_frame_count_divided_by_frame_rate` | 実装済み |
| fetch_voicevox_speakers | monkeypatchでHTTP呼び出しを差し替え、`/speakers` を呼び出してJSONを返す | `test_fetch_voicevox_speakers_calls_speakers_api_and_returns_json` | 実装済み |
| fetch_voicevox_speakers | monkeypatchでHTTP呼び出しを差し替え、`base_url` の末尾に `/` があっても正しいURLになる | `test_fetch_voicevox_speakers_handles_base_url_trailing_slash` | 実装済み |
| fetch_voicevox_speakers | monkeypatchで接続失敗を発生させ、`VoicevoxApiError` になる | `test_fetch_voicevox_speakers_connection_failure_raises_clear_error` | 実装済み |
| fetch_voicevox_speakers | monkeypatchでHTTPエラーを発生させ、`VoicevoxApiError` になる | `test_fetch_voicevox_speakers_http_error_raises_clear_error` | 実装済み |
| fetch_voicevox_speakers | monkeypatchで不正JSONレスポンスを返し、`VoicevoxApiError` になる | `test_fetch_voicevox_speakers_invalid_json_raises_clear_error` | 実装済み |
| resolve_speaker_id | 本物のVOICEVOX ENGINEには接続せず、`/speakers` の結果を模した `list[dict]` から話者名一致で最初の `style id` を返す | `test_resolve_speaker_id_returns_first_style_id_for_matching_speaker` | 実装済み |
| resolve_speaker_id | 本物のVOICEVOX ENGINEには接続せず、`/speakers` の結果を模した `list[dict]` と `aliases` で話者名を解決できる | `test_resolve_speaker_id_resolves_speaker_alias` | 実装済み |
| resolve_speaker_id | 本物のVOICEVOX ENGINEには接続せず、存在しない話者名で `VoicevoxApiError` になる | `test_resolve_speaker_id_missing_speaker_raises_voicevox_api_error` | 実装済み |
| resolve_speaker_id | 本物のVOICEVOX ENGINEには接続せず、`styles` が空の場合に `VoicevoxApiError` になる | `test_resolve_speaker_id_empty_styles_raises_voicevox_api_error` | 実装済み |
| resolve_speaker_id | 本物のVOICEVOX ENGINEには接続せず、`style id` が存在しない場合に `VoicevoxApiError` になる | `test_resolve_speaker_id_missing_style_id_raises_voicevox_api_error` | 実装済み |
| create_audio_query | monkeypatchでHTTP呼び出しを差し替え、`/audio_query` にPOSTし、`text` と `speaker_id` がクエリに入ることと正常時にJSON dictを返すことを確認する | `test_create_audio_query_posts_to_audio_query_and_returns_json` | 実装済み |
| create_audio_query | monkeypatchで接続失敗を発生させ、`VoicevoxApiError` になる | `test_create_audio_query_connection_failure_raises_voicevox_api_error` | 実装済み |
| create_audio_query | monkeypatchでHTTPエラーを発生させ、`VoicevoxApiError` になる | `test_create_audio_query_http_error_raises_voicevox_api_error` | 実装済み |
| create_audio_query | monkeypatchで不正JSONレスポンスを返し、`VoicevoxApiError` になる | `test_create_audio_query_invalid_json_raises_voicevox_api_error` | 実装済み |
| synthesize_wav | monkeypatchでHTTP呼び出しを差し替え、`/synthesis` にPOSTし、`audio_query` をJSONとして送り、正常時にbytesを返すことを確認する | `test_synthesize_wav_posts_to_synthesis_with_audio_query_json` | 実装済み |
| synthesize_wav | monkeypatchで接続失敗を発生させ、`VoicevoxApiError` になる | `test_synthesize_wav_connection_failure_raises_voicevox_api_error` | 実装済み |
| synthesize_wav | monkeypatchでHTTPエラーを発生させ、`VoicevoxApiError` になる | `test_synthesize_wav_http_error_raises_voicevox_api_error` | 実装済み |
| synthesize_wav | monkeypatchで空レスポンスを返し、`VoicevoxApiError` になる | `test_synthesize_wav_empty_response_raises_voicevox_api_error` | 実装済み |
| write_wav_bytes | 指定パスにWAVバイト列を書ける | `test_write_wav_bytes_writes_bytes_to_path` | 実装済み |
| write_wav_bytes | 親ディレクトリがなければ作成する | `test_write_wav_bytes_creates_parent_directories` | 実装済み |
| write_wav_bytes | 書き込み失敗時に対象パスが分かる例外になる | `test_write_wav_bytes_write_failure_includes_path` | 実装済み |
| synthesize_dialogue_wav | 本物のVOICEVOX ENGINEには接続せず、`create_audio_query` / `synthesize_wav` / `write_wav_bytes` / `read_wav_info` をmonkeypatchで差し替え、`DialogueEvent.voice_text` を使って `create_audio_query` を呼び、指定した `output_path` とWAV長を同じ `DialogueEvent` の `wav_path` / `duration_sec` に設定して返す | `test_synthesize_dialogue_wav_uses_voice_text_and_sets_wav_metadata` | 実装済み |
| synthesize_dialogue_wav | `create_audio_query` で失敗した場合に例外が伝播する | `test_synthesize_dialogue_wav_create_audio_query_error_propagates` | 実装済み |
| synthesize_dialogue_wav | `synthesize_wav` で失敗した場合に例外が伝播する | `test_synthesize_dialogue_wav_synthesize_wav_error_propagates` | 実装済み |
| synthesize_dialogue_wav | `write_wav_bytes` で失敗した場合に例外が伝播する | `test_synthesize_dialogue_wav_write_wav_bytes_error_propagates` | 実装済み |
| synthesize_dialogue_wav | `read_wav_info` で失敗した場合に例外が伝播する | `test_synthesize_dialogue_wav_read_wav_info_error_propagates` | 実装済み |
| synthesize_dialogue_wavs | 本物のVOICEVOX ENGINEには接続せず、`resolve_speaker_id` / `synthesize_dialogue_wav` をmonkeypatchで差し替え、複数の `DialogueEvent` を順番に `synthesize_dialogue_wav` へ渡し、`SilenceEvent` と `SoundEffectEvent` は処理せずそのまま残し、イベント順を維持し、`out_dir` を作成し、出力ファイル名がセリフ単位で連番になることを確認する | `test_synthesize_dialogue_wavs_synthesizes_dialogues_and_preserves_other_events` | 実装済み |
| synthesize_dialogue_wavs | 話者名やセリフにファイル名として使いにくい文字があっても `_` に置換された安全な名前になる | `test_synthesize_dialogue_wavs_sanitizes_output_filenames` | 実装済み |
| synthesize_dialogue_wavs | `resolve_speaker_id` で失敗した場合に例外が伝播する | `test_synthesize_dialogue_wavs_resolve_speaker_id_error_propagates` | 実装済み |
| synthesize_dialogue_wavs | `synthesize_dialogue_wav` で失敗した場合に例外が伝播する | `test_synthesize_dialogue_wavs_synthesize_dialogue_wav_error_propagates` | 実装済み |
| attach_sound_effect_info | 実際の効果音WAVファイルには依存せず、`read_wav_info` をmonkeypatchで差し替え、複数の `SoundEffectEvent` の `path` を順番に `read_wav_info` へ渡し、取得した `duration_sec` を `SoundEffectEvent.duration_sec` に設定し、`DialogueEvent` と `SilenceEvent` は処理せずそのまま残し、イベント順を維持する | `test_attach_sound_effect_info_reads_wav_info_and_preserves_event_order` | 実装済み |
| attach_sound_effect_info | `read_wav_info` で失敗した場合に例外が伝播する | `test_attach_sound_effect_info_read_wav_info_error_propagates` | 実装済み |
| concatenate_wavs | `tmp_path` と `wave` で作成した小さいWAVを使い、外部ファイルに依存せず、`DialogueEvent.wav_path`、`SilenceEvent.duration_sec` の無音、`SoundEffectEvent.path` をイベント順に連結し、出力先の親ディレクトリを作成し、連結後の `WavInfo` を返し、出力WAVのフレーム順にイベント順が反映されることを確認する | `test_concatenate_wavs_concatenates_events_in_order_and_returns_wav_info` | 実装済み |
| concatenate_wavs | WAV形式が一致しない場合に `ValueError` になる | `test_concatenate_wavs_mismatched_wav_format_raises_value_error` | 実装済み |
| concatenate_wavs | `DialogueEvent.wav_path` が未設定の場合に `ValueError` になる | `test_concatenate_wavs_unset_dialogue_wav_path_raises_value_error` | 実装済み |
| concatenate_wavs | 音声WAVが1つもない場合に `ValueError` になる | `test_concatenate_wavs_without_audio_wav_raises_value_error` | 実装済み |
| build_srt_cues | `SrtCue(index, start_sec, end_sec, text)` を使い、`current_sec` を0.0から積み上げ、複数の `DialogueEvent` から字幕キューを作り、`DialogueEvent` だけを `SrtCue` にし、`SilenceEvent.duration_sec` と `SoundEffectEvent.duration_sec` を字幕時刻に反映し、`SrtCue.index` が1から連番になり、`start_sec` / `end_sec` がdurationの積み上げで決まり、`subtitle_text` が字幕テキストになることを確認する | `test_build_srt_cues_builds_dialogue_cues_from_accumulated_durations` | 実装済み |
| build_srt_cues | `DialogueEvent.duration_sec` が未設定の場合に `ValueError` になる | `test_build_srt_cues_unset_dialogue_duration_raises_value_error` | 実装済み |
| build_srt_cues | `SoundEffectEvent.duration_sec` が未設定の場合に `ValueError` になる | `test_build_srt_cues_unset_sound_effect_duration_raises_value_error` | 実装済み |
| build_srt_cues | `subtitle_text` が空の場合に `ValueError` になる | `test_build_srt_cues_empty_subtitle_text_raises_value_error` | 実装済み |
| format_srt_timestamp | 0秒を `00:00:00,000` に整形できる | `test_format_srt_timestamp_formats_zero_seconds` | 実装済み |
| format_srt_timestamp | 秒とミリ秒をSRT時刻形式 `HH:MM:SS,mmm` に整形できる | `test_format_srt_timestamp_formats_seconds_and_milliseconds` | 実装済み |
| format_srt_timestamp | 1時間を超える値をSRT時刻形式に整形できる | `test_format_srt_timestamp_formats_over_one_hour` | 実装済み |
| format_srt_timestamp | 負数の場合に `ValueError` になる | `test_format_srt_timestamp_negative_seconds_raises_value_error` | 実装済み |
| format_srt | 複数の `SrtCue` をSRT本文文字列に変換し、キュー間に空行を入れ、末尾を改行で終える | `test_format_srt_formats_multiple_cues_with_blank_lines_and_trailing_newline` | 実装済み |
| format_srt | `end_sec` が `start_sec` より小さい場合に `ValueError` になる | `test_format_srt_end_before_start_raises_value_error` | 実装済み |
| format_srt | `text` が空の場合に `ValueError` になる | `test_format_srt_empty_text_raises_value_error` | 実装済み |
| format_srt | 空の `cues` を空文字列として扱う | `test_format_srt_empty_cues_returns_empty_string` | 実装済み |
| write_srt_file | 親ディレクトリがなければ作成し、指定パスにUTF-8でSRTを書き出せる | `test_write_srt_file_writes_utf8_srt_to_path` | 実装済み |
| generate_voicevox_assets | 本物のVOICEVOX ENGINEには接続せず、`read_script_file` / `parse_script` / `insert_gap_events` / `fetch_voicevox_speakers` / `synthesize_dialogue_wavs` / `attach_sound_effect_info` / `concatenate_wavs` / `build_srt_cues` / `write_srt_file` をmonkeypatchで差し替え、既存部品を正しい順番で呼び、`script_path`、`script_path.parent`、`default_gap`、`voicevox_url`、`out_dir`、`DEFAULT_SPEAKER_ALIASES`、`concat_path`、`srt_path` を主要引数として渡し、`concatenate_wavs` の `WavInfo` を返すことを確認する | `test_generate_voicevox_assets_calls_pipeline_functions_in_order` | 実装済み |
| main | CLI引数から `ScriptOptions` を作り、`generate_voicevox_assets` を呼び、成功時に終了コード0を返し、`audio_path` / `srt_path` / `duration_sec` を表示する | `test_main_builds_script_options_and_returns_zero_on_success` | 実装済み |
| main | `generate_voicevox_assets` が例外を投げた場合に終了コード1を返し、stderrへ `error: ...` を表示する | `test_main_returns_one_when_generate_voicevox_assets_raises` | 実装済み |

## 2. 追加検討したいテスト観点

| 対象 | 観点 | 理由 | 優先度 |
|---|---|---|---|
| parse_script | `||` がない場合に `voice_text` と `subtitle_text` が同一になることを独立して確認する | 現在も全角コロンのテスト内で間接的に確認しているが、字幕分離仕様として独立していると意図が読みやすい | 中 |
| parse_script | 効果音の相対パスが `script_dir` 基準で解決されることを明示的に確認する | 現在の効果音テストでも確認しているが、パス解決仕様として独立テスト化すると変更時に気づきやすい | 低 |
| synthesize_dialogue_wavs | `DialogueEvent` が0件の場合に `resolve_speaker_id` / `synthesize_dialogue_wav` を呼ばず、非セリフイベントだけを同順で返すことを独立して確認する | 現在は混在イベントの成功系で非セリフイベントを確認しているが、セリフ0件の境界条件として切り出すと意図が読みやすい | 低 |
| concatenate_wavs | 最初の音声WAVより前に `SilenceEvent` がある場合でも、基準WAV形式に合わせた無音として連結されることを独立して確認する | 現在の成功系は音声WAVの後に無音を置いて確認しているため、先頭無音の境界条件を分けると仕様が読みやすい | 低 |
| write_srt_file | 空の `cues` でも空のSRTファイルを書き出せることを独立して確認する | `format_srt([])` は空文字列として確認済みだが、ファイル書き出し側では空 `cues` をまだ直接確認していないため | 低 |
| parse_args | `--gap` と `--base_url` を省略した場合に既定値 `0.08` と `http://127.0.0.1:50021` が使われることを独立して確認する | 現在は `main` 経由で指定値の反映を確認しているが、既定値は独立テスト化するとCLI仕様が読みやすい | 中 |
| parse_args | 必須引数が不足した場合に argparse のエラーになることを確認する | 現在は正常系のCLI引数のみ確認しているため、CLI入口の基本的な失敗条件として確認余地がある | 低 |

## 3. 保留してよい観点

| 対象 | 観点 | 保留理由 |
|---|---|---|
| parse_script | 効果音ファイルの存在確認 | 今回の対象は台本解析までであり、効果音WAVの読み込み工程で扱うべき |
| parse_script | 効果音ファイルがWAV形式かどうかの確認 | 今回の対象外で、WAV情報取得や音声処理側の責務 |
| parse_script | VOICEVOX話者一覧との照合 | 今回の対象外で、VOICEVOX連携側の責務 |
| parse_script | `speed` や `pause` の数値妥当性 | 現段階では文字列パラメータ解析までが対象で、VOICEVOX query反映時に検証してもよい |
| parse_script | `volume`、`fade_in`、`fade_out` の数値妥当性 | 初期実装では効果音パラメータを音声加工へ反映しないため、後続工程で検討する |
| insert_gap_events | `DialogueEvent` と `SoundEffectEvent` の間にもgapを入れる仕様 | 現仕様では「まずは `DialogueEvent` 同士」が基本で、変更する場合は仕様判断が必要 |
| read_script_file | 文字コードの自動判定 | 仕様はUTF-8前提であり、初期実装では過剰 |

## 4. 今回は対象外の観点

| 対象 | 理由 |
|---|---|
| `話者.スタイル` 指定 | 初期実装の `resolve_speaker_id` では未対応であり、スタイル指定仕様が固まってから扱うため |
| 複数スタイルの選択 | 初期実装では話者名一致時に先頭の `style id` を返す方針であり、選択ルールが未確定のため |
| VOICEVOX実接続 | HTTP呼び出しはmonkeypatchで差し替えており、本物のVOICEVOX ENGINEへの接続は今回のテスト対象外のため |
| 効果音WAVの加工・連結 | 実ファイルの音声加工や連結は今回対象外であり、`attach_sound_effect_info` では `read_wav_info` による長さ取得までを扱うため |
| 動画生成 | 本機能の第1段階では扱わないため |
| GUI化 | CLIまたは関数利用を前提としており、今回の対象外のため |

## 5. 直近のpytest結果

```text
83 passed in 0.26s
```
