# VOICEVOX Video Tool

VOICEVOXを使って、YouTubeショート動画向けの音声・字幕素材を生成するための実験用ツールです。

短い台本を読み込み、VOICEVOX ENGINEでセリフ音声を生成し、WAV連結とSRT字幕生成までを段階的に確認できるようにしています。現時点ではCLI化前の実験段階で、主に関数単位の実装と手動確認スクリプトで動作を確認しています。

## できること

- UTF-8の台本ファイルを読み込む
- 台本を `DialogueEvent` / `SilenceEvent` / `SoundEffectEvent` に解析する
- セリフ間に通常の無音時間を挿入する
- VOICEVOX ENGINEから話者一覧を取得する
- 台本上の話者名をVOICEVOXのstyle idに解決する
- 1セリフ、または複数セリフのWAVを生成する
- 効果音WAVの長さを取得する
- セリフWAV、無音、効果音WAVを連結して `all.wav` 相当の音声を作る
- イベント列からSRTキューを作る
- SRT本文を整形し、UTF-8の `.srt` ファイルとして書き出す

## 必要な環境

- Python 3.13以上を想定
- pytest
- VOICEVOX ENGINE
  - 実接続を行う手動確認では `http://127.0.0.1:50021` で起動している前提です。

依存パッケージは以下でインストールできます。

```powershell
python -m pip install -r requirements.txt
```

## 基本的な使い方

現時点ではCLIはまだありません。基本的には `make_voicevox_assets.py` の関数を組み合わせて使います。

おおまかな処理順は以下です。

1. `read_script_file` で台本を読む
2. `parse_script` でイベント列にする
3. `insert_gap_events` でセリフ間の無音を入れる
4. `fetch_voicevox_speakers` でVOICEVOX話者一覧を取得する
5. `synthesize_dialogue_wavs` でセリフごとのWAVを生成する
6. `attach_sound_effect_info` で効果音WAVの長さを取得する
7. `concatenate_wavs` で全体音声を生成する
8. `build_srt_cues` で字幕キューを作る
9. `write_srt_file` でSRTを書き出す

## 手動確認スクリプト

主な手動確認スクリプトは以下です。

```powershell
python -m examples.manual_voicevox_test
python -m examples.manual_concatenate_test
python -m examples.manual_srt_test
python -m examples.manual_full_pipeline_test
```

- `examples/manual_voicevox_test.py`
  - 実際のVOICEVOX ENGINEに接続し、1セリフ分のWAV生成を確認します。
- `examples/manual_concatenate_test.py`
  - 外部ファイルやVOICEVOXに依存せず、小さいWAVを作って連結処理を確認します。
- `examples/manual_srt_test.py`
  - `SrtCue` を直接作り、SRTファイル書き出しを確認します。
- `examples/manual_full_pipeline_test.py`
  - VOICEVOX ENGINEに実接続し、短い台本からセリフWAV、`all.wav`、`output.srt` をまとめて生成します。

## 出力されるファイル

手動確認では主に `tmp/` 配下にファイルを出力します。

例:

- `tmp/manual_voicevox_test.wav`
- `tmp/manual_all.wav`
- `tmp/manual_output.srt`
- `tmp/full_pipeline/script.txt`
- `tmp/full_pipeline/wav/*.wav`
- `tmp/full_pipeline/all.wav`
- `tmp/full_pipeline/output.srt`

生成された `.wav` や `.srt` は `.gitignore` の対象です。

## GitHub Actionsでのチェック

`.github/workflows/python-checks.yml` で、pushおよびpull request時に以下を実行します。

- Python 3.13 のセットアップ
- `requirements.txt` のインストール
- `python -m compileall make_voicevox_assets.py tests examples`
- `python -m pytest tests/test_make_voicevox_assets.py`

## クレジット・ライセンスについて

このツールは VOICEVOX ENGINE に接続して音声を生成します。

生成した音声を公開・配布・動画利用する場合は、VOICEVOX公式規約および利用する音声ライブラリごとの規約を確認してください。

VOICEVOXを利用した音声には、利用した音声ライブラリに応じたクレジット表記が必要です。

例:

- VOICEVOX:ずんだもん
- VOICEVOX:四国めたん

このリポジトリのコードは、VOICEVOX本体・音声ライブラリ・キャラクター素材の権利を含みません。

生成した音声の利用可否は、利用者自身がVOICEVOX公式規約および各キャラクターの規約を確認してください。

このリポジトリ内のコードのライセンスは、リポジトリにライセンスファイルが追加されている場合はその内容に従ってください。ライセンスファイルがない場合、利用・再配布の扱いはリポジトリ管理者に確認してください。

## 注意事項

- このツールは実験用です。
- `examples/manual_voicevox_test.py` と `examples/manual_full_pipeline_test.py` はVOICEVOX ENGINEへの実接続が必要です。
- VOICEVOX ENGINEが起動していない場合、実接続を行うスクリプトは失敗します。
- 現時点ではCLIは未実装です。
- 動画生成は未実装です。
- 効果音の音量調整、fade in、fade outなどの加工は未実装です。
- WAV連結では、最初に登場した音声WAVの形式を基準にし、チャンネル数・サンプル幅・サンプリング周波数が一致しないWAVはエラーになります。
