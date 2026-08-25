# PC活動連動型デスクトップ箱庭アプリ 企画・要求仕様書 v0.1

**文書種別:** 企画・要求仕様書  
**バージョン:** v0.1  
**対象:** 企画・設計・実装担当者  
**初期対象OS:** Windows 11  
**想定実装:** Python / PySide6

---

# 1. 企画概要

## 1.1 仮称

**Keyboard Garden（仮）**

正式名称は別途決定する。

## 1.2 コンセプト

本アプリケーションは、ユーザーのPC上で発生するキーボード・マウス等の活動を匿名化したうえでゲーム世界への入力へ変換し、デスクトップ上に「そのセッションだけの箱庭世界」を生成する常駐型ジェネラティブ箱庭アプリケーションである。

ユーザーはゲームを進行させるために専用操作を繰り返す必要がない。

通常どおり、

- プログラミングする
- 文章を書く
- Webを閲覧する
- マウスを操作する
- ゲームをプレイする
- 考えて手を止める

といったPC活動そのものが世界へ影響する。

中心となる体験を次のように定義する。

> **普段のPC活動が、今日だけの小さな世界を作る。**

---

# 2. プロダクト原則

本アプリの設計・実装判断では以下の8原則を優先する。

## 2.1 Activity, not Content

取得した入力内容そのものではなく、入力の種類・量・速度・リズム等の「活動特性」を利用する。

## 2.2 Privacy by Design

Raw Inputを必要以上に保持しない。

ゲーム世界側から実際に入力された文字列やマウス位置を復元できない構造を基本とする。

## 2.3 Ambient First

本アプリのために本来のPC作業やゲームプレイを阻害してはならない。

「ゲームを遊ばせる」のではなく「PCを使っていたら横で世界が育っていた」という体験を優先する。

## 2.4 Ephemeral World

World Stateは原則としてアプリケーション起動ごとに新規生成する。

前回の世界を育成データとして継続することを基本ゲームループとしない。

## 2.5 Persistent Discovery

Worldそのものは消滅しても、発見した生物・植物・現象等の記録は永続化可能とする。

**「世界は消える、発見は残る」**を長期利用の基本方針とする。

## 2.6 Emergent, not Scripted

「Forestだから木を直接生成する」のような結果の直接指定を可能な限り避ける。

資源量・湿度・風等の条件を変化させ、その結果として森林等が形成されるシミュレーションを目指す。

## 2.7 Deterministic Core

World Seed、Tendency、World Trait、Activity Event等が同一なら、可能な範囲で同じ結果を再現できる決定論的シミュレーションを基本とする。

## 2.8 Content Driven

Tendency、生物、植物、Material、Event、Phenomenon等をゲーム本体へハードコードせず、将来的な有償・無償コンテンツ追加を考慮したデータ駆動構造とする。

---

# 3. 基本ゲームループ

```text
Application Start
        │
        ▼
Create New World
        │
        ├─ World Seed
        ├─ Today's Tendency
        └─ World Traits
        │
        ▼
Observe PC Activity
        │
        ├─ Keyboard
        ├─ Mouse
        └─ Idle / Time
        │
        ▼
Privacy Filter
        │
        ▼
Activity Model
        │
        ▼
World Interpreter
        │
        ├─ Matter
        ├─ Force
        └─ Time
        │
        ▼
World Simulation
        │
        ├─ Terrain
        ├─ Materials
        ├─ Plants
        ├─ Creatures
        └─ Environment
        │
        ▼
Events / Rare Phenomena
        │
        ▼
World evolves
```

このループをアプリケーション起動中継続する。

---

# 4. PC Activity Model

## 4.1 基本方針

ゲームシステムはWindows上のRaw Inputを直接参照しない。

入力層とゲーム世界の間にPrivacy FilterおよびActivity Aggregatorを配置する。

```text
Keyboard ──┐
            │
Mouse ──────┼── Raw Input Layer
            │
            ▼
      Privacy Filter
            │
            ▼
    Activity Aggregator
            │
            ▼
      Activity Model
            │
            ▼
     World Interpreter
```

---

# 5. キーボード入力

## 5.1 取得対象

アプリケーションがフォーカスされていない状態でも、ユーザー活動として必要なキーボードイベントを取得可能とする。

具体的なWindows APIについては技術PoCで決定する。

候補:

- Windows Raw Input
- 適切なWindows入力API
- 必要な場合のみLow-Level Keyboard Hook

入力遅延およびアンチチート等との互換性を優先して方式を決定する。

## 5.2 Privacy Filter

Raw Keyを長期間保持しない。

例えば、

```text
Raw Key: "A"
      ↓
Privacy Filter
      ↓
Category: LETTER
      ↓
Raw Key破棄
```

とする。

ゲーム側は原則として「Aが入力された」という事実を知らない。

## 5.3 入力カテゴリー候補

- LETTER
- NUMBER
- SYMBOL
- SPACE
- ENTER
- BACKSPACE
- MODIFIER
- OTHER

カテゴリー粒度はPrivacy要件とゲーム性を比較して最終決定する。

## 5.4 保存禁止情報

少なくとも以下を永続保存しない。

- 実入力文字列
- キー入力列
- パスワード等を復元可能な情報
- Raw Key Event履歴
- キー入力の詳細な時系列ログ

Telemetry等を将来導入する場合もRaw Inputを対象外とする。

---

# 6. マウス入力

## 6.1 基本方針

マウスもキーボード同様、Raw Eventを直接World Simulationへ渡さない。

## 6.2 利用候補情報

- 一定期間内の移動量
- 移動速度
- Click回数
- Scroll量
- Drag発生
- Activity / Idle判定

## 6.3 原則として保持しない情報

- マウス絶対座標
- クリック絶対座標
- マウス移動軌跡
- 操作対象アプリケーション
- Window Title等の作業内容推定情報

例:

```text
Raw Mouse Event
      ↓
移動差分を計算
      ↓
movement_level = HIGH
      ↓
Raw Coordinates破棄
```

---

# 7. Activity Aggregator

個々の入力イベントをWorldへ直接送信するのではなく、一定時間単位でActivityとして集約できる設計とする。

例:

```text
ActivityFrame
├─ keyboard_activity
├─ pointer_activity
├─ click_activity
├─ scroll_activity
├─ burstiness
├─ continuity
├─ idle_ratio
└─ session_duration
```

値は0.0～1.0等の正規化された指標として扱うことを検討する。

集約間隔は100ms～1000ms程度をPoCで比較する。

---

# 8. ActivityからWorldへの変換

基本概念を以下とする。

```text
Keyboard → Matter
Mouse    → Force
Idle     → Time
```

## 8.1 Keyboard / Matter

キーボード活動は主に世界へ物質・資源を供給する。

候補:

- Sand
- Soil
- Seed
- Food
- Mineral
- Water
- Special Material

## 8.2 Mouse / Force

マウス活動は主に既存世界へ力を与える。

候補:

- Wind
- Water Flow
- Diffusion
- Erosion
- Seed Transport
- Environmental Disturbance

例えばマウス移動が活発な場合、風が強まり、既に存在する種が遠くへ運ばれる等の間接的作用を優先する。

## 8.3 Idle / Time

操作の少ない時間を単なる「何も起きない時間」としない。

候補:

- 植物成長
- 生物の自由行動
- 睡眠
- 天候変化
- 昼夜変化
- 繁殖
- Rare Phenomenon判定

---

# 9. Activity Rhythm

総入力数だけではなく、入力のリズムも利用可能とする。

候補:

- intensity
- burstiness
- continuity
- idle_ratio
- keyboard/mouse ratio
- session_duration

例えば同じ1000回の入力でも、

```text
高速連続入力
```

と、

```text
入力
↓
思考
↓
入力
↓
思考
```

では異なるActivity Profileとなる。

ただし、Activity Profileから実際の入力内容を復元できないことを優先する。

---

# 10. Ambient InputとDirect Interaction

入力を以下の2種類へ分離する。

## 10.1 Ambient Input

他アプリケーション利用中に観測したPC Activity。

World形成の主要入力となる。

## 10.2 Direct Interaction

箱庭そのものに対するユーザー操作。

候補:

- 生物をクリックして観察
- 生物を撫でる
- WorldをZoom
- 軽微なオブジェクト移動

Direct Interactionによって発生した入力をAmbient Activityとして再計上しない。

自己フィードバックを防止する。

---

# 11. World Session

## 11.1 新規World

原則として、

**Application Start = New World**

とする。

## 11.2 World Seed

各WorldにSeedを持たせる。

Seedは以下に利用する。

- 初期条件
- ランダム選択
- Event判定
- Rare Phenomenon
- シミュレーション再現
- デバッグ

乱数生成を各機能から直接実行せず、Seed管理されたRandom Providerへ集約することを推奨する。

---

# 12. Today's Tendency

## 12.1 概要

Today's Tendencyは、そのセッションの世界形成傾向を決める主要なModifierである。

例:

- Random
- Forest
- Wetland
- Desert
- Crystal

## 12.2 設計方針

Tendencyはゲーム本体へハードコードしない。

```text
TendencyDefinition
       ↓
WorldModifier
       ↓
World Simulation
```

とする。

例えばForestは「木を生成する」のではなく、

```text
Soil Rate     +20%
Seed Rate     +30%
Humidity      +15%
Mineral Rate  -10%
```

等の環境条件を変更する。

その結果として森林が形成されやすくなる。

## 12.3 将来拡張

Tendencyは稼働後に有償・無償で追加できることを初期設計から考慮する。

将来候補:

- Snowfield
- Volcanic
- Sakura
- Aquarium
- Ruins
- Moonlight Garden
- Cyber Garden

---

# 13. World Traits

Tendencyとは別に、そのWorld固有の小さな特徴を付与可能とする。

例:

```text
Tendency:
Forest

Traits:
- Windy
- Mineral Rich
```

World Traitは、

- wind_multiplier
- humidity_modifier
- mineral_multiplier
- growth_modifier

等の小規模Modifierとして扱う。

これにより、

```text
Tendency × Traits × Activity
```

によって同じTendencyでも異なる世界を生成する。

---

# 14. Material System

Materialをデータとして定義する。

初期候補:

- Sand
- Soil
- Seed
- Food
- Mineral
- Water

MVPでは必要最小限に削減してよい。

Materialは以下のような属性を持てる構造を検討する。

- density
- mobility
- fertility
- moisture
- nutrition
- rarity
- interaction_tags

---

# 15. Falling Object / Fragmentation

入力活動によって生成された一部の資源は、画面上部から視覚的オブジェクトとして落下させる。

```text
Activity
   ↓
Spawn Object
   ↓
Fall
   ↓
Collision
   ↓
Fragmentation
   ↓
Material
```

初期実装では高度なポリゴン破砕を要求しない。

GlyphやSymbolのマスクから複数粒子を生成し、元オブジェクトを削除する方式を利用可能とする。

実際のキー文字をGlyphとして使用する必要はない。

Privacy Filter後のカテゴリーに対応した抽象図形・粒子等を表示する。

---

# 16. Sand / Grid Simulation

大量粒子をすべてRigid Bodyとして処理しない。

推奨方式:

```text
Falling Object
      ↓
Physics Engine

Large Fragment
      ↓
Physics Engine

Small / Static Particle
      ↓
Grid / Cellular Automaton
```

砂等については、

- 真下へ落下
- 真下が塞がっていれば斜め下へ移動
- 移動不能なら静止

等の簡易ルールから開始する。

---

# 17. Environmental Recipe

結果を直接生成するのではなく、Materialと環境条件の組み合わせから現象を発生させる。

例:

```text
Soil + Seed + Water
        ↓
       Plant
```

```text
Mineral + Pressure
        ↓
      Crystal
```

```text
Sand + Strong Wind
        ↓
       Dune
```

Recipe / Rule自体も将来的にデータ駆動化できる構造を検討する。

---

# 18. Plant System

植物は最低限以下のライフサイクルを持てるものとする。

```text
Seed
 ↓
Germination
 ↓
Plant
 ↓
Growth
```

成長条件として以下を利用可能とする。

- Soil
- Water
- Humidity
- Temperature
- Time
- Tendency
- World Trait

MVPでは植物数種類程度から開始する。

---

# 19. Creature System

## 19.1 MVP

初期バージョンでは生物1種類から開始可能とする。

## 19.2 基本行動

候補:

```text
Idle
Walk
SearchFood
Eat
Play
Sleep
```

初期AIはFinite State Machine等の単純な方式でよい。

## 19.3 データ駆動

CreatureDefinitionをゲームロジックから分離する。

候補属性:

- id
- movement
- preferred_food
- preferred_environment
- activity_pattern
- traits
- behavior_profile
- asset_id

将来的に生物追加をコンテンツとして扱える構造とする。

---

# 20. Event System

Eventを独立したシステムとして扱う。

例:

```text
大量のKeyboard Activity
        ↓
Activity Condition成立
        ↓
Rain Event
```

```text
長時間Idle
        ↓
Quiet Night
```

EventDefinition候補:

- Trigger
- Conditions
- Probability
- Cooldown
- Effect
- Presentation

イベント処理をWorld本体へ個別ハードコードしないことを推奨する。

---

# 21. Rare Phenomenon

低確率で珍しい自然現象・生物・構造物等が発生可能とする。

候補:

- Rainbow
- Meteor
- Aurora
- Rare Creature
- Giant Flower
- Ancient Ruin

Rare Phenomenonは強力な報酬として扱う必要はない。

「気付いたら珍しいものが発生していた」という発見体験を優先する。

---

# 22. Session Milestone

World内で起きた重要な出来事を静かに提示できるようにする。

候補:

- First Bloom
- First Creature
- First Rain
- First Nest
- Sunset

作業を妨害する大型Popup等は避ける。

---

# 23. Discovery

World Stateとは別にDiscovery情報を永続保存可能とする。

候補:

```text
Discovery
├─ Plants
├─ Creatures
├─ Phenomena
├─ World Traits
└─ Tendencies
```

Discoveryは長期利用の軽いモチベーションとして利用する。

ゲーム進行上必須の収集作業にはしない。

---

# 24. 表示モード

World SimulationとViewを分離する。

```text
                 WorldSimulation
                       │
# 24\. 表示モード

World SimulationとViewを分離する。

```text
                 WorldSimulation
                       │
                       ▼
                 View Adapter
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   Desktop View    Window View    Preview View
```

## 24\.1 Desktop View

デスクトップ上に箱庭を常時表示する基本モード。

候補:

- 透明背景
- 枠なしウィンドウ
- 常に最前面
- クリック透過
- 画面端への配置
- マルチモニター対応

他アプリケーションの操作を妨げないことを優先する。

## 24\.2 Window View

通常のウィンドウとして表示するモード。

候補:

- サイズ変更
- 最大化
- 最小化
- タイトルバー表示
- 通常のマウス操作
- 詳細情報パネル表示

設定変更やDiscovery確認時の基本画面とする。

## 24\.3 Preview View

常駐中にWorldの状態を簡易表示する小型ビュー。

候補:

- タスクトレイからのプレビュー
- 小型フローティングウィンドウ
- 現在のTendency表示
- Activity状態表示
- 直近のMilestone表示

## 24\.4 表示品質

表示品質は以下の段階を持てる構造とする。

- Low
- Medium
- High
- Automatic

低負荷時は高品質表示を許可し、PC負荷が高い場合は自動的に描画品質を下げる。

---

# 25\. UI構成

## 25\.1 基本方針

UIはWorldの観察を主目的とし、情報過多にならないようにする。

常時表示する情報は最小限とする。

## 25\.2 メイン画面

メイン画面には以下を表示可能とする。

- World View
- Today’s Tendency
- World Trait
- 現在時刻またはWorld Time
- Activity状態
- ミュート状態
- 設定ボタン
- Discoveryボタン
- 終了ボタン

## 25\.3 Activity表示

Activityの詳細な入力履歴は表示しない。

表示候補:

- Quiet
- Calm
- Active
- Intense

または抽象的なゲージ・光・粒子等で表現する。

## 25\.4 Tendency表示

Today’s Tendencyは初回起動時および必要に応じて確認できる。

表示例:

```text
Today's Tendency: Forest
Traits: Windy / Mineral Rich
```

## 25\.5 Discovery画面

Discovery画面では以下を確認できる。

- 発見済み項目
- 未発見項目のシルエットまたは伏字
- 発見日時
- 発見したWorldのTendency
- 発見回数
- 説明文

実入力内容や操作対象アプリケーション等は表示しない。

## 25\.6 通知

通知は控えめな表示を基本とする。

候補:

- 画面端の小型バナー
- タスクトレイ通知
- World内の視覚演出
- サウンドによる短い通知

通知は設定で無効化可能とする。

---

# 26\. 常駐動作

## 26\.1 タスクトレイ常駐

アプリケーションはWindowsタスクトレイへ常駐可能とする。

タスクトレイメニュー候補:

- Worldを表示
- Worldを非表示
- 一時停止
- Activity取得の停止
- Discoveryを開く
- 設定を開く
- 今日のWorldを終了
- アプリケーション終了

## 26\.2 自動起動

Windowsログイン時の自動起動を設定可能とする。

初期値はユーザーが選択できるものとし、無断で有効化しない。

## 26\.3 一時停止

一時停止中は以下を停止または抑制する。

- キーボードActivity取得
- マウスActivity取得
- World Simulation
- Event判定
- 通知

一時停止前のWorld Stateは、設定に応じてメモリ上に保持するか破棄する。

## 26\.4 非表示

Worldを非表示にしても、Activity取得およびSimulationを継続するか選択可能とする。

初期値は以下を推奨する。

- 非表示中もSimulationは継続
- Activity取得は継続
- ユーザーが停止可能

## 26\.5 スリープ・ロック・サインアウト

以下の状態を検知可能とする。

- PCロック
- スリープ
- 休止状態
- サインアウト
- シャットダウン

状態に応じてWorld Timeを停止または経過させる。

初期仕様では、PCが利用不能な時間はSimulationを停止し、復帰時に再開する方式を推奨する。

---

# 27\. 設定

## 27\.1 設定画面

設定はカテゴリごとに整理する。

- 一般
- 表示
- Activity
- サウンド
- 通知
- プライバシー
- パフォーマンス
- データ
- 詳細

## 27\.2 一般設定

候補:

- Windowsログイン時に起動
- タスクトレイへ最小化
- 起動時にWorldを表示
- 起動時に前回の表示位置を復元
- 終了確認を表示
- 言語

## 27\.3 表示設定

候補:

- Desktop View / Window View
- 常に最前面
- クリック透過
- 不透明度
- 表示サイズ
- マルチモニター対象
- アニメーション品質
- FPS上限
- 背景表示
- UI表示・非表示

## 27\.4 Activity設定

候補:

- キーボードActivity取得
- マウスActivity取得
- Click取得
- Scroll取得
- Idle時間の扱い
- Activity反映量
- Activity取得の一時停止ショートカット

各項目は初期値を安全側に設定する。

## 27\.5 サウンド設定

候補:

- サウンド有効・無効
- マスターボリューム
- 環境音ボリューム
- Event音量
- Rare Phenomenon音量
- Windows通知音の使用

## 27\.6 通知設定

候補:

- Milestone通知
- Rare Phenomenon通知
- Discovery通知
- タスクトレイ通知
- 通知の表示時間
- 集中モード

## 27\.7 プライバシー設定

ユーザーが取得対象を明示的に確認できるようにする。

表示項目:

- 取得する入力種別
- 保存されるデータ
- 保存されないデータ
- Activity集約間隔
- Raw Inputを保存しないこと
- アプリケーション名やWindow Titleを取得しないこと

## 27\.8 パフォーマンス設定

候補:

- Simulation品質
- 描画品質
- 最大粒子数
- 最大生物数
- FPS上限
- CPU使用率上限
- バックグラウンド時の更新頻度
- バッテリー節約モード

## 27\.9 データ設定

候補:

- Discoveryデータの保存場所を開く
- Discoveryデータのエクスポート
- Discoveryデータのインポート
- Discoveryデータの初期化
- 設定の初期化
- キャッシュの削除

---

# 28\. データ保存

## 28\.1 保存対象

永続保存可能なデータは以下に限定する。

- Discovery
- ユーザー設定
- 表示位置・サイズ
- アプリケーションバージョン
- コンテンツバージョン
- 必要最小限の統計情報
- エラー診断情報

## 28\.2 保存しないデータ

以下は永続保存しない。

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

## 28\.3 World State

World Stateは原則としてセッション終了時に破棄する。

ただし、デバッグまたはユーザーが明示的に保存を選択した場合に限り、匿名化された再現用データを保存可能とする。

保存する場合も以下を含めない。

- Raw Input
- 実入力内容
- マウス座標
- 他アプリケーション情報

## 28\.4 保存形式

設定およびDiscoveryはJSON、SQLite等のローカル形式を利用可能とする。

候補構成:

```text
data/
├─ settings.json
├─ discovery.json
├─ content/
├─ cache/
└─ logs/
```

実装時にはWindowsのユーザーデータ保存領域を利用し、インストールディレクトリへユーザーデータを直接保存しない。

## 28\.5 原子性

保存処理中にアプリケーションが終了してもデータ破損を防止する。

推奨方式:

1. 一時ファイルへ書き込み
2. 書き込み完了を確認
3. 既存ファイルをバックアップまたは置換
4. 一時ファイルを削除

## 28\.6 バージョン管理

保存データにはスキーマバージョンを含める。

将来のアップデート時には、旧形式から新形式へのマイグレーションを実行可能とする。

---

# 29\. コンテンツ管理

## 29\.1 データ駆動構造

以下の定義を外部データとして管理可能とする。

- TendencyDefinition
- WorldTraitDefinition
- MaterialDefinition
- PlantDefinition
- CreatureDefinition
- EventDefinition
- PhenomenonDefinition
- RecipeDefinition

## 29\.2 コンテンツ検証

起動時またはコンテンツ読み込み時に以下を検証する。

- 必須IDの存在
- IDの重複
- 参照先の存在
- 数値範囲
- 必須画像・音声の存在
- スキーマバージョン
- 不正な循環参照

不正なコンテンツがあっても、可能な限り他のコンテンツで起動を継続する。

## 29\.3 追加コンテンツ

将来的な有償・無償コンテンツ追加を考慮する。

ただし、初期バージョンでは外部コンテンツの自動ダウンロードや実行可能コードの読み込みを行わない。

---

# 30\. エラー処理

## 30\.1 基本方針

エラー発生時も、可能な限り以下を維持する。

- ユーザーの通常操作
- World Viewの表示
- Discoveryデータ
- 設定データ
- プライバシー保護

## 30\.2 入力取得エラー

キーボードまたはマウス入力の取得に失敗した場合:

- Activity取得を停止
- World Simulationは可能な範囲で継続
- ユーザーへ簡潔な通知を表示
- 再試行を行う
- Raw Inputを代替保存しない

## 30\.3 描画エラー

描画処理に失敗した場合:

- 描画品質を下げる
- GPU依存機能を無効化する
- Window Viewへ切り替える
- SimulationとViewを分離してSimulationを継続する
- 復旧不能時は安全に表示を停止する

## 30\.4 データ保存エラー

保存に失敗した場合:

- 一時ファイルを残して復旧を試みる
- 既存の正常なデータを上書きしない
- ユーザーへ保存失敗を通知する
- 次回終了時または一定時間後に再試行する
- Raw Inputをエラー情報へ含めない

## 30\.5 コンテンツエラー

コンテンツ定義が不正な場合:

- 該当コンテンツを無効化
- 代替コンテンツまたはデフォルト値を使用
- エラー内容を開発者向けログへ記録
- ユーザーには必要最小限の通知を行う

## 30\.6 予期しない例外

予期しない例外発生時は、アプリケーション全体を即時終了させるのではなく、以下の単位で隔離する。

- Input Layer
- Activity Aggregator
- World Simulation
- Renderer
- Audio
- Persistence
- UI

重大な破損が疑われる場合は、World Stateを破棄して安全に再起動できるようにする。

## 30\.7 ログ

ログには以下を記録可能とする。

- 発生日時
- アプリケーションバージョン
- OSバージョン
- エラー種別
- スタックトレース
- 機能モジュール
- 設定された品質レベル

ログには以下を記録しない。

- Raw Input
- 実入力文字列
- マウス座標
- Window Title
- 操作対象アプリケーション
- 画面内容

---

# 31\. セキュリティおよびプライバシー

## 31\.1 最小権限

アプリケーションは必要最小限の権限で動作する。

管理者権限を必須としない。

## 31\.2 入力監視の明示

初回起動時に、キーボード・マウスActivityを取得することを明示する。

ユーザーが同意しない場合でも、以下の限定モードで起動可能とする。

- Direct Interactionのみ
- Activity取得なし
- World Simulationのみ

## 31\.3 Raw Inputの即時破棄

Raw Inputはカテゴリー化または集約に必要な処理後、速やかに破棄する。

メモリ上に保持する場合も短時間・限定量とする。

## 31\.4 機密入力への配慮

パスワード入力等を内容として取得しない。

入力カテゴリー化を行う場合も、実文字列やキー列を保存・送信しない。

必要に応じて以下の機能を提供する。

- Activity取得の一時停止
- 特定ショートカットによる停止
- タスクトレイからの停止
- ユーザーによる完全無効化

## 31\.5 外部通信

初期バージョンでは外部通信を必須としない。

外部通信を導入する場合は、以下を明示する。

- 通信目的
- 送信データ
- 保存期間
- 第三者提供の有無
- 無効化方法

Raw Inputおよびそれから復元可能な情報は外部送信しない。

## 31\.6 コンテンツの安全性

外部コンテンツは実行可能コードとして扱わない。

画像、音声、定義データ等の許可された形式のみ読み込む。

## 31\.7 データ削除

ユーザーは設定画面から以下を削除できる。

- Discovery
- キャッシュ
- ローカルログ
- 設定
- すべてのアプリケーションデータ

削除前には確認を表示する。

---

# 32\. 性能要件

## 32\.1 基本目標

通常のオフィス作業中に、ユーザー体験および他アプリケーションの操作を阻害しないこと。

## 32\.2 CPU使用率

目標値:

- アイドル時平均: 1%未満
- 通常Simulation時平均: 3%未満
- 短時間のEvent発生時: 10%未満を目安
- 高負荷時は自動的に品質を下げる

測定環境は別途定義する。

## 32\.3 メモリ使用量

目標値:

- 起動直後: 150MB未満
- 通常稼働時: 300MB未満
- 長時間稼働時に単調増加しない

メモリリーク検証を実施する。

## 32\.4 描画性能

目標値:

- Window View: 60FPSを目標
- Desktop View: 30FPS以上を目標
- 低負荷モード: 15FPS以上
- FPS上限を設定可能

## 32\.5 入力遅延

Activity取得が他アプリケーションの入力遅延を発生させない。

目標:

- 入力取得処理による追加遅延を体感できない水準
- ActivityFrame生成は設定された集約間隔内に完了
- 入力処理が詰まった場合はWorld側への反映を間引く

## 32\.6 長時間稼働

最低8時間以上の連続稼働試験を行う。

確認項目:

- メモリ増加
- CPU使用率の増加
- 描画停止
- Activity取得停止
- World Simulationの不安定化
- Discovery保存失敗

## 32\.7 負荷制御

以下の制御を実装可能とする。

- 最大粒子数
- 最大生物数
- Event同時実行数
- Simulation更新頻度
- 描画更新頻度
- バックグラウンド更新頻度
- 画面外オブジェクトの簡略化

---

# 33\. 互換性およびアクセシビリティ

## 33\.1 対象環境

初期対象:

- Windows 11 64bit
- 一般的なキーボード・マウス
- シングルモニターおよびマルチモニター

## 33\.2 表示スケーリング

Windowsの表示倍率100%、125%、150%、200%でUIが破綻しないこと。

## 33\.3 アクセシビリティ

候補:

- キーボードのみで設定操作
- 高コントラスト表示
- 色覚多様性に配慮した配色
- アニメーション軽減
- 点滅表現の抑制
- サウンドなしでも状態を確認可能
- 通知の無効化

---

# 34\. テスト方針

## 34\.1 単体テスト

対象:

- Privacy Filter
- Activity Aggregator
- Activity Profile計算
- Seed付き乱数
- Recipe判定
- Plant成長
- Creature AI
- Event判定
- Discovery保存
- 設定保存
- データマイグレーション

## 34\.2 結合テスト

対象:

- InputからActivityへの変換
- ActivityからWorldへの変換
- World SimulationからViewへの反映
- EventからDiscoveryへの反映
- 設定変更から各モジュールへの反映

## 34\.3 プライバシーテスト

以下を確認する。

- Raw Inputがログに出ない
- Raw Inputが保存されない
- マウス座標が保存されない
- Window Titleを取得しない
- クリップボードを取得しない
- 外部通信へ入力情報が含まれない
- メモリダンプから不要な入力履歴が長期間残らない

## 34\.4 性能テスト

以下を確認する。

- 8時間以上の連続稼働
- 最大粒子数での描画
- 最大生物数でのSimulation
- 高頻度Activity
- 長時間Idle
- マルチモニター
- 高DPI
- PCロック・スリープ復帰

## 34\.5 互換性テスト

対象候補:

- Windows 11各種更新状態
- 一般的なIME
- 日本語・英語キーボード
- 高負荷アプリケーション併用
- フルスクリーンゲーム併用
- アンチチート搭載ゲーム併用

入力取得方式が他アプリケーションへ影響しないことを確認する。

---

# 35\. 受け入れ基準

## 35\.1 起動・終了

- Windows 11上で起動できる
- 初回起動時に必要な権限・Activity取得について説明される
- 起動時に新しいWorldが生成される
- タスクトレイへ常駐できる
- ユーザー操作で安全に終了できる
- 終了時にDiscoveryおよび設定が破損なく保存される

## 35\.2 Activity連動

- キーボードActivityがカテゴリー化され、Worldへ反映される
- マウスActivityが集約され、Worldへ反映される
- Idle時間がWorldの時間経過や成長へ反映される
- 実入力文字列がWorldへ表示されない
- マウス絶対座標がWorldへ表示されない
- Direct InteractionがAmbient Activityとして二重計上されない

## 35\.3 World生成

- World Seedがセッションごとに生成される
- Today’s Tendencyが表示される
- World Traitが適用される
- 同一Seedおよび同一Activity入力で再現可能な結果が得られる
- World Stateが原則としてセッション終了時に破棄される

## 35\.4 Simulation

- Materialが生成される
- Falling Objectまたは同等の視覚的反応が発生する
- Gridまたは同等の簡易物理で資源が堆積する
- Plantが条件に応じて成長する
- Creatureが最低1種類動作する
- Eventが条件に応じて発生する
- Rare Phenomenonが低確率で発生可能である

## 35\.5 UI

- Desktop ViewとWindow Viewを切り替えられる
- Worldを非表示にできる
- Activity取得を一時停止できる
- Discoveryを確認できる
- 通知およびサウンドを無効化できる
- 高DPI環境でUIが崩れない
- 設定を再起動後も保持できる

## 35\.6 データ保存

- Discoveryが再起動後も保持される
- 設定が再起動後も保持される
- 保存中断時に既存データが破損しない
- データスキーマバージョンが管理される
- ユーザーがDiscoveryおよび設定を削除できる
- Raw Inputが保存されない

## 35\.7 エラー処理

- 入力取得失敗時にアプリケーション全体が即時終了しない
- 描画失敗時に低品質または代替表示へ移行できる
- 保存失敗時に既存データを保護する
- 不正コンテンツを読み込んでも可能な範囲で起動を継続する
- エラーログにプライバシー情報が含まれない

## 35\.8 性能

- 通常稼働時に他アプリケーションの操作を阻害しない
- 8時間以上の連続稼働で重大なメモリリークがない
- 通常稼働時のメモリ使用量が目標値以内である
- FPSが設定値または最低目標値を下回り続けない
- 高負荷時に自動的な負荷制御が機能する

## 35\.9 セキュリティ・プライバシー

- 管理者権限なしで動作する
- Activity取得の有効・無効をユーザーが選択できる
- Raw Inputを外部送信しない
- クリップボード、画面、Window Titleを取得しない
- ユーザーが保存データを削除できる
- 外部コンテンツから実行可能コードを読み込まない

---

# 36\. MVP範囲

初期MVPでは以下を必須とする。

- Windows 11対応
- タスクトレイ常駐
- キーボードActivityのカテゴリー化
- マウス移動量の集約
- ActivityからMaterialへの変換
- Falling Objectまたは簡易粒子表現
- Gridベースの簡易Simulation
- Plant数種類
- Creature 1種類
- Today’s Tendency数種類
- World Trait数種類
- Discovery保存
- 基本設定
- Activity取得の一時停止
- Raw Input非保存
- 基本的なエラー処理
- 基本的な性能制御

以下はMVP後の候補とする。

- 高度な破砕表現
- 複雑なCreature AI
- 多数のRare Phenomenon
- 外部コンテンツ配信
- 有償コンテンツ
- クラウド同期
- 詳細なリプレイ
- 複数Worldの同時表示
- 高度なマルチモニター演出

---

# 37\. 未決事項

以下はPoCおよび技術検証で決定する。

- Raw Input取得方式
- Low\-Level Keyboard Hook採用可否
- IME環境での入力分類
- アンチチート搭載ゲームとの互換性
- Desktop Viewのクリック透過方式
- 描画方式
- Physics Engine採用可否
- Grid Simulationの更新頻度
- Activity集約間隔
- World Timeの進行速度
- World Stateのデバッグ保存形式
- Discoveryのデータ形式
- コンテンツ定義形式
- 自動起動の実装方式
- 外部通信の導入可否
- ライセンスおよび配布方式

---

# 38\. 開発フェーズ

## Phase 1: 技術PoC

- キーボード・マウスActivity取得
- Privacy Filter
- Activity Aggregator
- タスクトレイ常駐
- 最小限のWorld View
- Seed付きSimulation
- Raw Input非保存の検証

## Phase 2: Simulation Prototype

- Material
- Falling Object
- Grid Simulation
- Plant
- Creature
- Event
- Tendency
- World Trait

## Phase 3: Product Prototype

- UI
- 設定
- Discovery
- データ保存
- エラー処理
- 性能制御
- 一時停止
- Desktop View

## Phase 4: MVP Release Candidate

- 受け入れ基準の実施
- 長時間稼働試験
- プライバシー監査
- 互換性試験
- インストーラー
- アンインストール
- ユーザー向けドキュメント

---

# 39\. 成功指標

本アプリの成功は、単純なプレイ時間や入力回数だけで評価しない。

候補指標:

- 初回起動後にWorldを観察したユーザー割合
- 1セッションあたりの平均観察時間
- Discoveryを発見したユーザー割合
- Activity取得を継続して有効化している割合
- 通知・表示による作業中断の少なさ
- クラッシュ率
- 長時間稼働時の安定性
- プライバシー設定への理解度
- 「普段の作業がWorldへ反映された」と感じる割合

最終的には、以下の体験が成立していることを重視する。

> ユーザーが特別な操作をしなくても、PCを使っている間に世界が変化し、ふと画面を見たときに小さな発見がある。