# 小さなラボラトリー

小さなラボラトリーは、普段のPC活動に応じて素材が届き、錬金術師の女の子が小さなラボで実験・観察・記録を進める、Windows向けデスクトップ実験マスコットです。

リポジトリ名とPythonパッケージ名は互換性維持のため **Miniatured World / miniatured-world** を継続します。

## コンセプト

普段のPC活動が、今日の小さな実験素材になる。

本アプリは、キーボードカテゴリ量、ポインタ移動量、クリック、スクロール、操作リズム、アイドル時間など、抽象化された活動特徴だけを扱います。入力文字列そのものや作業内容を素材・実験内容として使う設計にはしません。

## 現在の状態

現在のリリース済みベースライン: **V0.8 / v0.8.2**

現在の作業候補: **V0.9 / v0.9.0 小さなラボラトリーへの表現リメイク**

V0.4 では、ローカル実行できるコア、アプリ実行基盤、実行コマンド、PySide6 のウィンドウ表示・設定・発見画面を実装しました。

V0.5 では、設定の永続化、既定データ保存先、設定画面からの設定更新、Qtトレイメニュー、CLIの一時実行モード、ユーザー向けアウトプットの日本語統一を実装しました。

V0.6 では、Windowsから安全に取得できる最小の実活動信号として、Raw Inputを扱わないWindowsアイドル取得元、活動取得状態表示、取得元選択CLIを実装しました。

V0.7 では、表示モード、最前面、クリック透過、不透明度の設定をPySide6ウィンドウ属性へ反映するデスクトップ表示PoCを実装しました。

V0.8 では、MVP RC本体ではなくRC準備版として、Windows実活動Provider、PyInstaller exeビルド手順、MIT License、プライバシー監査と実機検証手順を追加しました。

V0.8.1 では、GUIイベントループ、Qt描画、ウィンドウ更新を含めたGUIあり8時間安定性検証ログ出力と自動終了を追加し、PySide6 6.9系で作成した単体exeによる実機8時間検証を完了しました。PySide6 6.10系で作成したexeはGUI起動に失敗するため、配布ビルドは確認済みのPySide6 6.9系に固定します。

V0.8.2 では、MVP RC前の表示・非干渉品質を狭く固めるため、Windowsでのクリック透過補助、表示設定テスト、表示・トレイ復帰の検証手順を追加しました。

V0.9.0 では、ユーザー向け表現を箱庭世界から「小さなラボラトリー」へ切り替え、基準背景、錬金術師の女の子、錬金釜、素材エフェクトを別レイヤーとして扱う初期ラボ表示を追加します。

まだMVP RC合格宣言、全環境で保証された完全クリック透過、インストーラー、コード署名、自動更新は含みません。

## プロダクト原則

- **内容ではなく活動**: 入力文字列や作業内容ではなく、活動特徴だけを使う。
- **プライバシーを設計の前提にする**: Raw Input、キー入力列、マウス座標、Window Title、画面キャプチャ、クリップボード内容を永続保存しない。
- **通常作業を邪魔しない**: 通常作業やゲームプレイを妨げない。
- **ラボはセッション単位**: アプリ起動ごとに、その日のラボ状態を生成する。
- **発見情報は残せる**: セッション状態は消えても、発見した反応や記録は残せる。
- **台本ではなく創発**: 活動が条件を変え、素材や実験反応が生まれる。
- **再現可能な中核**: seed、傾向、特性、活動フレームから再現できる設計を優先する。
- **コンテンツはデータ駆動**: 傾向、素材、植物、生物、レシピ、イベント、現象はデータ駆動化を前提にする。

## 初期ターゲット

- OS: Windows 11 64-bit
- 言語/ランタイム: Python
- UIフレームワーク: PySide6
- アプリ形態: デスクトップ常駐 / ウィンドウ / トレイ
- 初期シミュレーション: 素材供給、錬金釜反応、錬金術師キャラクター状態、イベント、発見の永続化

## リポジトリ構成

```text
assets/                 画像・音声・素材の配置場所
config/                 設定テンプレート
docs/                   企画、要求、ADR、設計メモ
docs/adr/               Architecture Decision Records
scripts/                開発補助スクリプト
src/miniatured_world/   アプリケーション本体
tests/unit/             単体テスト
tests/integration/      結合テスト
```

## ローカル開発

テスト実行:

```powershell
python -m pytest
```

UIなしでプライバシー安全なスモーク実行:

```powershell
$env:PYTHONPATH='src'
python -m miniatured_world --no-ui --ephemeral --frames 5
```

デモ活動取得元を明示して実行:

```powershell
$env:PYTHONPATH='src'
python -m miniatured_world --no-ui --ephemeral --frames 5 --activity-provider demo
```

活動取得元は `auto`、`demo`、`none`、`windows-idle`、`windows-global` から選べます。`windows-idle` はWindowsの最終入力時刻からアイドル時間だけを取得するPoCです。`windows-global` はWindows Raw Inputを即時にカテゴリ、移動量、クリック、スクロールへ変換する実活動取得元です。どちらも入力文字列、キー列、座標、Window Title、画面キャプチャ、クリップボード内容は保存しません。

Windows実活動取得を明示して実行:

```powershell
$env:PYTHONPATH='src'
python -m miniatured_world --no-ui --ephemeral --frames 5 --activity-provider windows-global
```

Settings画面の表示設定では、`window` / `desktop` / `preview` の表示モード、常に最前面、クリック透過、不透明度を変更できます。`desktop` はフレームレス、ツールウィンドウ、最前面、透明背景を適用します。Windowsではクリック透過有効時にOSの拡張ウィンドウスタイルも補助的に適用します。ただし、全アプリ・全環境での完全透過保証は後続検証に残しています。

PySide6 がインストール済みの場合、既定の入口は Qt ウィンドウ表示を起動します。

```powershell
$env:PYTHONPATH='src'
python -m miniatured_world
```

既定では、設定と発見情報はユーザーのローカルアプリデータ領域へ保存します。テストや一時確認では `--ephemeral`、保存先を明示したい場合は `--data-root <path>` を使います。

Windows以外、またはWindows実活動取得を初期化できない環境では、安全な取得不能状態またはデモ取得元へフォールバックします。

メイン画面の「ラボ」タブでは、同梱した基準背景の上に、錬金釜、錬金術師の女の子、素材流入、反応光、煙を別レイヤーで描画します。PC活動は素材供給や実験反応に変換されますが、入力内容や作業内容は使いません。

## 配布ビルド

PyInstallerを使うWindows向けexeビルド手順を用意しています。

```powershell
python -m pip install -e ".[ui,packaging]"
.\scripts\build_windows_exe.ps1
```

GUI配布ビルドでは、PySide6 が `>=6.7,<6.10` の範囲に収まっていることを確認してください。生成物は `dist\MiniaturedWorld.exe` です。V0.8ではmsi等のインストーラー、コード署名、自動更新は含みません。

## 安定性検証ログ

8時間安定性検証では、exeからJSONL形式の診断ログを出力できます。

```powershell
.\dist\MiniaturedWorld.exe --no-ui --ephemeral --activity-provider windows-global --duration-seconds 28800 --tick-interval-ms 1000 --realtime --stability-log logs\v0.8.0-stability-8h.jsonl
```

GUIありで8時間安定性検証を行う場合は、`--no-ui` を付けずに実行します。

```powershell
.\dist\MiniaturedWorld.exe --ephemeral --activity-provider windows-global --duration-seconds 28800 --tick-interval-ms 1000 --stability-log logs\v0.8.1-gui-stability-8h.jsonl
```

ログにはProvider状態、summary、World状態、CPU時間、メモリ使用量を記録します。入力文字列、キー列、座標、Window Title、画面内容、クリップボード内容は記録しません。

## 正本仕様

現在の正本仕様は以下です。

- [PC活動連動型デスクトップ箱庭アプリ 企画・要求仕様書 v0.1](docs/PC活動連動型デスクトップ箱庭アプリ%20企画・要求仕様書%20v0.1.md)
- [ADR 0002: 小さなラボラトリー表示リメイク](docs/adr/0002-little-laboratory-visual-remake.md)

実装判断が README と競合する場合は、仕様書と OODA の決定記録を優先します。

## 開発方式

本プロジェクトは OODA ワークフローで進めます。

1. Observe: 変更せずに証拠を集める。
2. Orient: 証拠を解釈し、必要に応じて計画系ドキュメントを更新する。
3. Decide: スコープ、Acceptance Criteria、Release Contract を確定する。
4. Act: 実装、検証、文書化、リリースを行う。

詳細なエージェント運用ルールは [AGENTS.md](AGENTS.md) を参照してください。

## プライバシーベースライン

以下は永続保存しません。

- Raw Keyboard Event
- 実入力文字列
- キー入力列
- マウス絶対座標
- マウス移動軌跡
- クリック座標
- 操作対象アプリケーション
- Window Title
- 画面キャプチャ
- クリップボード内容

このベースラインを弱める機能は、実装前に明示的な OODA Decide を必要とします。

V0.8では外部通信、テレメトリ、クラウド同期、外部コンテンツ配信は未実装です。将来導入する場合も、通信目的、送信データ、無効化方法を明示し、Raw Inputや復元可能な情報は送信しません。

## ライセンスとサポート

ライセンスは [MIT License](LICENSE) です。

サポート方針は、個人開発の実験版としてGitHub Issueのみです。互換性保証、個別環境サポート、商用サポートは現時点では提供しません。

## 実装済みの中核機能

- サニタイズ済み活動イベント
- キーボードカテゴリ化
- ポインタ移動量の集約
- Direct Interaction と Ambient Activity の分離
- 正規化された活動フレーム
- バンドル済みデータ駆動コンテンツ定義
- seed付きラボセッション生成
- 素材生成
- 簡易素材シミュレーション
- 錬金術師キャラクター状態表示
- 錬金釜ギミック状態表示
- 素材流入、反応光、煙のエフェクト表示
- イベントと希少現象のフック
- 原子的JSON設定保存
- 発見情報の保存
- 既定データ保存先
- 活動プロバイダー抽象
- Runtime の一時停止、再開、活動取得切替
- プライバシー安全なUIスナップショット
- 発見管理
- グループ化された設定モデル
- 表示、停止、活動取得、ミュート、終了の実行コマンド
- PySide6 のウィンドウ表示・設定・発見画面
- 表示設定をQtウィンドウ属性へ反映するデスクトップ表示PoC
- Qtトレイメニュー基盤
- 活動取得状態モデル
- Windowsアイドル取得元PoC
- Windows実活動Provider
- CLIの活動取得元選択
- World画面の活動取得状態表示
- offscreen Qt スモークテスト
