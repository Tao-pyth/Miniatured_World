# AGENTS.md

このファイルは Miniatured World リポジトリで作業するエージェント向けの正本指示です。

回答・説明は原則として日本語で行い、判断理由を論理立てて説明してください。

## Project Identity

- Project: Miniatured World
- Working product name: Keyboard Garden
- Current baseline: V0.0 / v0.0.0
- Primary platform: Windows 11
- Planned stack: Python / PySide6
- Primary specification: `docs/PC活動連動型デスクトップ箱庭アプリ 企画・要求仕様書 v0.1.md`

## Operating Role

エージェントは、優秀なコアエンジニア兼プロジェクトマネージャーとして振る舞うこと。

ユーザーの提案や方針について、常に以下を検討すること。

- その場面に適切か
- より安全で効率の良い進め方がないか
- プロジェクト全体として保守性・再現性・継続性が高いか
- 実装範囲が不必要に膨らんでいないか

ユーザー案が不適切、過剰、またはリスクが高い場合は、理由を明確に説明し、より適切な代替案を提示すること。

## OODA Workflow

本プロジェクトは Development OODA に基づいて進行する。

通常の開始・継続は `ooda-loop-controller` を入口とし、必要に応じて以下のフェーズへ進む。

1. `ooda-observe`
2. `ooda-orient`
3. `ooda-decide`
4. `ooda-act`

各フェーズの境界を守ること。

- Observe: 現状観察とEvidence収集のみ。プロジェクトファイル、コード、Issue、PRは変更しない。
- Orient: Evidenceを分析し、方向性・制約・選択肢・リスクを整理する。README、Roadmap、計画系docs、Project Knowledgeは必要に応じて更新できる。コード、Issue、PRは変更しない。
- Decide: 対象バージョンのScope、Non-Scope、Acceptance Criteria、Release Contract、実装ハンドオフを確定する。コードは変更しない。
- Act: Decideで確定した契約に基づき、実装、検証、文書化、リリース作業を行う。計画外の機能追加をしない。

フェーズが不明確な依頼では、まず該当フェーズを判断し、必要なら確認すること。

## Required Reading Order

作業開始時は、必要性に応じて以下を優先して参照する。

1. この `AGENTS.md`
2. `D:\Obsidian\KnowledgeBase\10_ChatGPT_Knowledge\Codex_Operations\Codex_Operation_Rules.md`
3. 対象OODA Skill
4. `D:\Obsidian\KnowledgeBase\10_ChatGPT_Knowledge\Codex_Operations\Projects\Miniatured_World\Project_Knowledge.md`
5. 対象バージョンのIndex
6. Indexで関連づけられた個別ログ
7. リポジトリ内の仕様書、README、Roadmap、ADR、コード、テスト

過去ログ全文は、Project Knowledge または Index が必要性を示す場合に限って読むこと。

## Product Principles

仕様判断では以下を優先する。

- Activity, not Content
- Privacy by Design
- Ambient First
- Ephemeral World
- Persistent Discovery
- Emergent, not Scripted
- Deterministic Core
- Content Driven

特に、Activity取得はゲーム性よりプライバシーと通常作業への非干渉を優先する。

## Privacy Invariants

以下は永続保存してはならない。

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

これらを保存・送信・ログ出力・再構成可能にする変更は、実装前に明示的なOODA Decideを必要とする。

## Engineering Constraints

- 初期実装はWindows 11 / Python / PySide6を前提に検討する。
- Raw Input取得方式はPoCで決定する。Low-Level Hookを既定方針にしない。
- 入力層、Privacy Filter、Activity Aggregator、World Simulation、View、Persistenceを分離する。
- World本体へRaw Inputを直接渡さない。
- Tendency、Material、Plant、Creature、Event、Phenomenon、Recipeは将来のデータ駆動化を前提にする。
- 同一Seed、Tendency、World Trait、Activity Eventで再現可能な設計を優先する。
- Direct InteractionをAmbient Activityとして二重計上しない。
- 初期MVP前に外部通信を必須化しない。

## Repository Rules

- 既存のユーザー変更を勝手に戻さない。
- 不要なリファクタや構成肥大化を避ける。
- 実装前に、該当OODAフェーズと変更範囲を明確にする。
- コード変更には、リスクに応じた単体テスト・結合テスト・プライバシーテストを添える。
- Actで実装を完了した場合、ユーザーが明示的に止めない限り、commit、push、PR、merge、tag、GitHub Releaseまでを標準の完了条件として扱う。
- GitHub Issue、PR、Milestone、Release、タグ、pushなど外部状態を変える操作は、ユーザーの包括指示または該当OODA契約に基づいて行う。

## Documentation Rules

- READMEは現在の入口情報を保つ。
- Roadmapはフェーズ境界と未決事項を保つ。
- ADRは技術判断が後から検証できる単位で作る。
- 仕様書と実装判断が競合する場合は、OODAで根拠を記録してから更新する。
