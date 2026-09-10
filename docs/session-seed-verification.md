# v0.9.8 起動ごとのSeedと再現

GUI・CLIとも `--seed` を省略すると、起動ごとに新しいseedを生成する。同じ初期条件で実行したいときは明示する。

```powershell
python -m miniatured_world --seed 20260825
python -m miniatured_world --no-ui --ephemeral --activity-provider demo --seed 20260825
```

exeも同じ引数を受け付ける。0や負数も有効。旧版で省略時の固定値を使っていたコマンドには `--seed 20260825` を追加する。

再現には同じseedだけでなく同じ活動入力・コンテンツが必要。現在のseedはCLI要約、または明示した `--stability-log` のsnapshot.seedに含まれる。異なるseedでも傾向・特性が同じになる場合がある。

## 検証

全148テストが合格（既存135＋追加13）。

- 偽乱数で異なる値を順に返し、GUI/CLIとも起動ごとに一度だけ生成して渡すことを検査する。
- 明示20260825・0・負数では乱数源を呼ばない。ヘルプ・不正な引数でも生成しない。
- GUIのImportErrorによるCLIフォールバックでは、同じ解決済みseedを再利用する。
- 実GUI/CLIプロセスで生成したseedを診断ログから取り、同じdemo活動で指定し直した最終World snapshotが一致することを検査する。
- 既存135テストを回帰し、初回活動選択、既存ON/OFF、設定・発見、一時実行を継承する。

すべての実行検査で `MINIATURED_WORLD_DATA_DIR` を専用検査先へ上書きし、ユーザーの既存データへ触れない。Windows配布exeのGUI15秒・CLIの省略/明示/0/負数、wheelのコード/素材一致とexe184素材一致を確認し、公開exe/SHA256の再取得後にも検証する。実測・公開証拠はOODA v0.9.7 Act loop 002、詳細ログは `logs/session-seed-v0.9.8`。

配布前の実測: 生成seedによるGUI15.275秒・同じseedの再実行15.272秒で、最終World snapshotが一致した。CLIも生成→同じseedの再指定、0、-42、20260825を各5フレーム実行し合格。7ケースすべて一時実行のデータディレクトリを作らない。wheelの226コード/素材ファイルとソース、exeの184素材のバイト一致を確認した。

exe: 52,555,534 bytes、SHA256 `b7f3da00de1e5e5ba638bff78d7df56f7ab958064caa8e66d23701ff4a4e1ca5`。

画像・アニメーション・World内部の生成ロジック・保存形式は不変。素材セットはv0.9.5、アプリはv0.9.8。V1全体や新版8時間運転の合格とはしない。[設計判断](adr/0010-session-seed.md)。
