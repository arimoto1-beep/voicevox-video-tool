# 長いDialogueEvent分割のパイプライン接続設計

## 1. 目的

長い `DialogueEvent` の分割処理を、既存のVOICEVOX音声生成パイプラインへどこで接続するかを設計する。

第48回までに、単体の `DialogueEvent` を分割する `split_long_dialogue_event` と、イベント列全体に適用する `split_long_dialogue_events` は実装済みである。今回は、それらを既存パイプラインへ組み込む前に、差し込み位置、CLI仕様、既存出力への影響、テスト観点を整理する。

今回は設計のみで、コード実装は行わない。

## 2. 背景

現在の素材生成パイプラインでは、台本ファイルからイベント列を作り、`DialogueEvent` / `SilenceEvent` / `SoundEffectEvent` をもとに以下を生成している。

- セリフごとのWAV
- 全体連結WAV
- SRT字幕
- 必要に応じたffmpeg動画生成

既存の大まかな処理順は以下である。

```txt
台本ファイル
  ↓
read_script_file
  ↓
parse_script
  ↓
insert_gap_events
  ↓
synthesize_dialogue_wavs
  ↓
attach_sound_effect_info
  ↓
concatenate_wavs
  ↓
build_srt_cues
  ↓
write_srt_file
```

長い字幕が画面外に切れる問題に対して、ASS側の簡易折り返しだけでは限界があった。特に2行を超える長文では、最後の行に残りがまとまり、結局画面外に切れる可能性が残る。

そのため、表示側だけで調整するのではなく、VOICEVOXへ投げる前に長い発話単位を短い発話単位へ分割する方針を取る。

## 3. 現在の問題

長い `DialogueEvent` をそのままVOICEVOXへ投げると、1つの長いWAVと1つの長いSRTキューが生成される。

この状態でASS側だけを折り返しても、字幕の表示幅は多少改善できるが、長すぎるセリフそのものは分割されない。ASS側で複数の `Dialogue:` に分ける案もあるが、1つの音声内でどの文字が何秒で読まれるかは分からないため、音声との同期は近似になる。

一方、VOICEVOX投入前に `DialogueEvent` を分割すれば、分割後のセリフごとにWAVが生成される。各WAVの長さからSRT時刻を作れるため、音声と字幕の同期を自然に保ちやすい。

ただし、分割を既存パイプラインへ常時適用すると、既存のWAVファイル数、ファイル名、all.wav、SRTのキュー数、動画の字幕タイミングが変わる。まずは安全側に倒し、デフォルト無効のオプション機能として扱う。

## 4. 方針

短期方針は以下とする。

- `--split-long-dialogue` が指定された場合だけ、長い `DialogueEvent` 分割を有効にする。
- デフォルトでは分割しない。
- 分割はVOICEVOX音声生成前に行う。
- まずは `voice_text == subtitle_text` の `DialogueEvent` のみ分割対象にする。
- `voice_text != subtitle_text` の `DialogueEvent` は分割対象外のままにする。
- `SilenceEvent` と `SoundEffectEvent` は分割しない。
- 既存の台本フォーマット、SRT仕様、ASS仕様は変更しない。
- 既存の `--ass-wrap-chars` / `--ass-max-lines` は、分割後字幕を画面内に収める補助として残す。

差し込み位置は、まず `parse_script` の直後、`insert_gap_events` の前を推奨する。

理由は、分割後の連続 `DialogueEvent` 間にも通常のgapを挿入できるためである。長い1文を複数の読み上げ単位に分ける場合、VOICEVOXのWAV同士が完全に詰まるより、既存の通常gapルールに乗せる方が安全である。

ただし、この場合は分割によって新たなgapが増えるため、all.wavの総時間は元より長くなる可能性がある。この差分は、`--split-long-dialogue` 指定時の意図した挙動として扱う。

## 5. 処理フロー

推奨する処理順は以下である。

```txt
台本ファイル
  ↓
read_script_file
  ↓
parse_script
  ↓
必要な場合だけ split_long_dialogue_events
  ↓
insert_gap_events
  ↓
VOICEVOX音声生成
  ↓
WAV連結
  ↓
SRT生成
```

実装イメージは以下である。

```python
events = parse_script(lines, options.script_path.parent)

if options.split_long_dialogue:
    events = split_long_dialogue_events(
        events,
        max_chars=options.dialogue_split_chars,
        min_chars=options.dialogue_split_min_chars,
    )

events = insert_gap_events(events, options.default_gap)
```

この位置に差し込むことで、分割後のイベント列を既存の音声生成・WAV連結・SRT生成パイプラインへそのまま渡せる。

代替案として、`insert_gap_events` の後に分割する位置も考えられる。この場合、分割されたセリフ同士には通常gapが入らないため、元の総尺に近づきやすい。ただし、分割後の読み上げ単位同士が詰まりすぎる可能性がある。まずは安全側として、`insert_gap_events` の前に差し込む案を優先する。

## 6. CLI仕様案

追加候補のCLI引数は以下である。

### --split-long-dialogue

長い `DialogueEvent` の自動分割を有効にするフラグ。

- 型: boolフラグ
- デフォルト: `False`
- 指定なし: 従来どおり分割しない
- 指定あり: `split_long_dialogue_events` を音声生成前に適用する

デフォルト無効にする理由は、既存出力との差分が大きいためである。分割を有効にすると、個別WAV数、all.wavの長さ、SRTキュー数、字幕タイミングが変わる可能性がある。

### --dialogue-split-chars

1つの `DialogueEvent` の目安文字数。

- 型: int
- デフォルト案: `18`
- `--split-long-dialogue` 指定時に使用する
- `max_chars <= 0` は `ValueError`

初期値は断定せず、まずは手動確認で調整する。ショート動画では14から20文字程度が候補になるが、VOICEVOXの読み上げ自然さ、字幕サイズ、画面幅によって変わる。

### --dialogue-split-min-chars

分割後に短すぎる断片を作らないための最小文字数。

- 型: int
- デフォルト案: `6`
- `--split-long-dialogue` 指定時に使用する
- `min_chars < 0` は `ValueError`
- `min_chars > dialogue_split_chars` は `ValueError`

短すぎる断片は、字幕として読みづらく、VOICEVOXの発話単位としても不自然になりやすい。まずは安全側として、短すぎる断片を避ける。

## 7. 分割対象と対象外

分割対象は `DialogueEvent` のみとする。

対象:

- `voice_text == subtitle_text` の `DialogueEvent`
- `voice_text` の長さが `dialogue_split_chars` を超えるもの

対象外:

- `voice_text != subtitle_text` の `DialogueEvent`
- `SilenceEvent`
- `SoundEffectEvent`
- その他の非Dialogueイベント

`voice_text != subtitle_text` を対象外にする理由は、読み上げテキストだけを分割すると字幕との対応が崩れるためである。

たとえば以下のような台本では、読み上げと表示字幕が別物である。

```txt
めたん：こんにちはなのです || こんにちは。
```

このイベントを自動分割すると、どの読み上げ断片にどの字幕断片を対応させるべきかが曖昧になる。短期実装では、この曖昧さを避けるため、読み上げと字幕が異なるイベントは手動で台本側を分ける方針にする。

## 8. 既存出力への影響

`--split-long-dialogue` 未指定時は、既存出力を変えない。

未指定時に維持するもの:

- 個別WAV数
- 個別WAVファイル名の並び
- all.wavの長さ
- SRTキュー数
- SRTタイミング
- 既存動画生成結果

`--split-long-dialogue` 指定時は、以下の差分が発生する可能性がある。

- 長いセリフが複数の `DialogueEvent` になる
- 個別WAV数が増える
- 分割後WAVのファイル名に同じ `line_no` 由来の名前が複数出る可能性がある
- `insert_gap_events` 前に分割する場合、分割後セリフ間にもgapが入る
- all.wavの総時間が変わる可能性がある
- SRTキュー数が増える
- SRTの各キューが短くなる
- ffmpeg側で焼き込まれる字幕も短くなる

これらは、フラグ指定時の明示的な挙動として扱う。

特に注意する点は、個別WAVファイル名である。既存のファイル名生成がイベント順 index を含むなら衝突しにくいが、`line_no` だけに強く依存している場合は、分割後の複数イベントで名前衝突が起きないことを確認する必要がある。

## 9. テスト観点

次回実装時は、少なくとも以下を確認する。

### parse_args / ScriptOptions

- `--split-long-dialogue` 指定時に `split_long_dialogue` が `True` になること
- 未指定時は `False` になること
- `--dialogue-split-chars` が指定値として入ること
- `--dialogue-split-min-chars` が指定値として入ること
- 未指定時にデフォルト値が入ること

### generate_voicevox_assets

- `split_long_dialogue=False` の場合、`split_long_dialogue_events` が呼ばれないこと
- `split_long_dialogue=True` の場合、`parse_script` 後、`insert_gap_events` 前に `split_long_dialogue_events` が呼ばれること
- 分割後イベント列が `insert_gap_events` に渡ること
- 分割後イベント列が `synthesize_dialogue_wavs` に渡ること
- `SilenceEvent` / `SoundEffectEvent` の順序が維持されること
- `voice_text != subtitle_text` のイベントは分割されないこと
- `max_chars <= 0`、`min_chars < 0`、`min_chars > max_chars` のエラーが伝播すること

### 出力差分

- フラグ未指定時に既存テストの期待値が変わらないこと
- フラグ指定時に個別WAV生成対象が増えること
- フラグ指定時にSRTキュー数が増えること
- 分割後のSRT時刻が各WAV長に基づいて作られること
- 分割後セリフ間に通常gapが入ること

## 10. 手動確認観点

手動確認では、以下を見る。

- 長いセリフが複数の個別WAVとして生成されること
- all.wavで分割後セリフのつながりが不自然すぎないこと
- 分割後セリフ間のgapが長すぎないこと
- output.srtのキューが短くなっていること
- SRTタイミングが音声と大きくずれないこと
- ffmpegで焼き込んだ字幕が画面外に切れにくくなること
- `--ass-wrap-chars` / `--ass-max-lines` と組み合わせたときに読みやすいこと
- 読み上げと字幕が異なるイベントが勝手に分割されていないこと
- SEや間イベントの位置が変わっていないこと

手動確認コマンドの例は、次回実装後に更新する。想定としては、既存の `make_voicevox_assets.py` 実行コマンドに以下を追加する。

```powershell
--split-long-dialogue `
--dialogue-split-chars 18 `
--dialogue-split-min-chars 6
```

## 11. 今回やること

今回やることは、この設計書を作成することだけである。

- 差し込み位置を整理する
- CLI仕様案を整理する
- 既存出力への影響を整理する
- テスト観点を整理する
- 手動確認観点を整理する

## 12. 今回やらないこと

今回は以下を実装しない。

- CLI引数追加
- `ScriptOptions` へのフィールド追加
- `generate_voicevox_assets` への分割処理組み込み
- 既存音声生成パイプラインの変更
- SRT生成処理の変更
- ASS生成処理の変更
- VOICEVOX呼び出し処理の変更
- 自然言語処理による高精度分割
- 文字幅ベースの分割
- 音素・発話タイミング解析
- VOICEVOX側の詳細タイミング取得
- 話者情報つき字幕キュー
- 立ち絵
- 口パク

## 13. 次回以降の実装方針

次回実装するなら、最小実装は以下とする。

1. `ScriptOptions` に以下を追加する。
   - `split_long_dialogue: bool = False`
   - `dialogue_split_chars: int = 18`
   - `dialogue_split_min_chars: int = 6`
2. `parse_args` に以下を追加する。
   - `--split-long-dialogue`
   - `--dialogue-split-chars`
   - `--dialogue-split-min-chars`
3. `generate_voicevox_assets` で、`parse_script` 後、`insert_gap_events` 前に条件付きで `split_long_dialogue_events` を呼ぶ。
4. 既存の未指定時挙動が変わらないことをテストする。
5. 指定時に分割後イベント列が後続処理へ渡ることをテストする。

まずは安全側として、デフォルト無効のまま導入する。実際の手動確認で、分割文字数、最小文字数、gapの入り方、字幕の見た目を確認し、必要なら次の段階で調整する。
