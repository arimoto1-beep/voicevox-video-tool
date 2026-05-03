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

## 2. 追加検討したいテスト観点

| 対象 | 観点 | 理由 | 優先度 |
|---|---|---|---|
| parse_script | `||` がない場合に `voice_text` と `subtitle_text` が同一になることを独立して確認する | 現在も全角コロンのテスト内で間接的に確認しているが、字幕分離仕様として独立していると意図が読みやすい | 中 |
| parse_script | 効果音の相対パスが `script_dir` 基準で解決されることを明示的に確認する | 現在の効果音テストでも確認しているが、パス解決仕様として独立テスト化すると変更時に気づきやすい | 低 |

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
| `synthesize_dialogue_wavs` | まだ複数イベントを処理して `DialogueEvent.wav_path` / `duration_sec` を設定する段階ではないため |
| 効果音WAV読み込み | 実ファイルの音声処理は今回対象外のため |
| WAV連結 | 今回の対象外であり、イベント列にgapを挿入するところまでを確認するため |
| SRT生成 | SRT時刻計算はWAV長取得後の工程であり、今回の対象外のため |
| 動画生成 | 本機能の第1段階では扱わないため |
| GUI化 | CLIまたは関数利用を前提としており、今回の対象外のため |
