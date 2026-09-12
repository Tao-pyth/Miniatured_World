# ADR 0012: OS休止と手動停止を分離する

状態: 採用。対象: v0.9.10。

実機確認でロック中もWorldが進行した。本人はロック中停止と解除後の元状態復帰をV1前の必須条件として承認した。

Runtimeは一時的なOS休止理由を集合で持つ。手動pausedや永続設定を上書きせず、snapshotでは有効な停止状態とsystem_pausedを示す。理由の追加/削除は冪等で、ロックと電源休止が重なっても早期再開しない。終了済みRuntimeを復活させない。

Qtの非表示受信窓をメイン画面から独立させる。WTS登録は自セッションに限定し、初期状態を照会する。失敗時は説明付き休止と5秒ごとの再試行。メイン画面を閉じる・表示モードを変える操作では受信窓を破棄せず、アプリ終了で登録解除する。

休止境界で集約済み活動を破棄する。Raw Inputバックエンドは休止中の通知を解釈せず既定処理へ返し、前後で待機メッセージとキューを破棄する。Deferred Providerはこの操作だけで生成しない。Worldへ生入力を渡さない。データの保存形式やCLIを変更しない。

WTSINFOEXは数値プレフィックスだけを参照し、名前等を読み取らない。ポインター幅と8byte境界を明示し、APIの出力サイズ/level/flagsを検証してメモリを解放する。

一次資料: [WTS登録](https://learn.microsoft.com/en-us/windows/win32/api/wtsapi32/nf-wtsapi32-wtsregistersessionnotification)、[セッション変更通知](https://learn.microsoft.com/en-us/windows/win32/termserv/wm-wtssession-change)、[状態構造体](https://learn.microsoft.com/en-us/windows/win32/api/wtsapi32/ns-wtsapi32-wtsinfoex_level1_w)、[電源復帰通知](https://learn.microsoft.com/en-us/windows/win32/power/pbt-apmresumeautomatic)。
