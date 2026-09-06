# 手元の連続原画（v0.9.5）

組み込みのImageGenで生成した原画と、再現用のプロンプトを保存する。CLI/API経由の画像生成は使用していない。`prompts.json` と `additional-prompts.json` が入力文の正本。

原画から128×128・接地基準120・既存64色へ整形する。人物の手と瓶は独立素材。瓶は空/内容入りで同じ外形を使う。採用前の比較や不採用の原画も、生成の経緯を確認できるよう残している。

## 採用方針

- 読む13コマ、取る16コマ、調合16コマ、置く16コマ。表示時間の配列は別に持つ。
- 重複を除いた全身原画は合計44種類。取得/配置の屈み原画は共有するが、逆再生や再使用を原画数へ重複計上しない。配置専用の立位・復帰原画も使う。
- 全系列の頭部を共通の原画から合成し、顔・帽子の生成差を固定する。屈み時は原画の首の位置に接続する。腕や指は各原画に由来する。
- 読書と調合の下腿を共通化し、植えた足の輪郭を安定させる。屈む動作は異なる膝・腰の原画を使う。
- 歩行は取得の終端と同じ上半身と、v0.9.4の距離同期された脚8コマを合成する。運搬から作業へ瓶が飛ばない持ち手を継承する。
- 手前の指マスクは同じ全身PNGの画素を抽出する。再量子化で近接色が変わらないよう、既にパレット内の画素はそのまま保存する。
- シート全体の再生成では屈み→立位の中割りが不足したため、`collect-lower.png` / `collect-rise.png` として部分系列を生成した。
- `mix-reach-sheet.png` は釜口の外側へ下がっていた回収の腕を修正した原画。`mix-sheet.png` は比較用。
- `walk-empty-sheet.png` で瓶を分離した頭部を採用した。追加の持ち手修正生成は脚まで変わったため不採用とし、従来の脚を維持した。

## 再現・検査

```powershell
.venv/Scripts/python.exe scripts/build_hand_sprites.py
.venv/Scripts/python.exe scripts/check_hand_candidates.py
.venv/Scripts/python.exe scripts/render_hand_candidates.py
```

候補素材は `logs/hand-motion-v0.9.5/candidate-assets`、判定は `candidate-check.json`、背景合成と通常/低速GIFは `candidate-preview` へ出力する。これらの合格だけでは、時間制御・受け渡し・配布物を含むリリース全体の合格にはしない。
