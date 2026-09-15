# ADR 0021: 起動登録と通常ウィンドウの配置

- 状態: 採用、v0.9.19
- 基準: v0.9.18
- 根拠: OODA Observe001 → Orient001 → Decide001「起動設定とウィンドウ位置」

## 問題

一般設定の位置復元とログイン起動は値だけを保存しており、実際の作用がなかった。どちらも既存の保存保護・削除・一時実行と接続する必要がある。

## 採用

位置は`WindowSettings(saved,x,y,width,height)`として既存Settings/JsonStoreへ保存する。位置は自分のウィンドウの枠左上、サイズは内容領域のQt論理単位。負の座標と有界の正のサイズを検証する。旧設定の項目欠落は未保存扱い、不正な構造は原本を保護する。

Qtの移動・リサイズを300msまとめ、通常位置のみを保持する。終了/トレイ退避前に反映する。自動更新は明示的設定変更のforce保存を使わず、設定保存/復元のONと既存Store保護に従う。画面との交差で復元先を選び、タスクバーを除いた利用可能範囲と枠のサイズへ収める。中央の内容はスクロール可能にして小画面でも操作を保つ。

Windows実機では、枠あり/なし切替後にQWidgetの位置情報が枠の変更に追いつかず、再表示で位置がずれた。位置取得と設定をQWindowの`framePosition`/`setFramePosition`へ統一し、実Windowsのモード往復を検証した。余分な待機時間に依存しない。

自動起動は現在利用者のHKCU Runと専用所有記録を使う。保存先の正規化パスから値名を作り、他の項目を列挙・変更しない。起動時の読取りと明示操作による登録変更を分け、旧設定のTrueから無断登録しない。UIは登録状態を表示し、Windows側の有効/無効は尊重する。

所有記録は`Software\MiniaturedWorld\Startup`の当該値へ保存する。更新途中は旧/新commandの両方を保持し、Run値との一致を確認してから次の操作へ進む。途中失敗でも自分の登録を解除・再試行できる。未知の値・所有不一致・外部変更は保護し、OS登録が成功したか不明なら状態不明を表示する。これは外部ソフトによる同時変更と原子的に排他する仕組みではない。

配布版は永続exe、Sourceは同じインストール先を確認したpythonwの隔離モードで起動する。Source登録時にGUI依存関係も確認する。引数は当該保存先のみを追加し、seed/診断/期限/一時実行を継承しない。Windowsの260 UTF-16単位制限を守る。設定関連の削除は登録解除を先に行い、解除失敗なら設定を残して独立した兄弟対象だけを処理する。

## 不採用と残る範囲

QSettingsへの別保存、旧True値による自動登録、全利用者の登録、シェルスクリプト、所有不明の登録削除は採用しない。物理ログイン・全DPI/多画面構成、共有保存先全体の複数プロセス排他は別の検証課題であり、短時間の成功から保証しない。

## 参照

- [Qt ウィンドウ幾何の復元](https://doc.qt.io/qt-6/restoring-geometry.html)
- [QWindow フレーム位置](https://doc.qt.io/qt-6/qwindow.html#setFramePosition)
- [Windows Run/RunOnce](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys)
- [Windows スタートアップ設定](https://support.microsoft.com/en-us/windows/experience/startup-boot/configure-startup-applications-in-windows)
