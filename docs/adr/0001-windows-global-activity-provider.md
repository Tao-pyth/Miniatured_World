# ADR 0001: Windows実活動Provider

## Status

Accepted for `v0.8.0` RC準備版。

## Context

`v0.8.0` では、アプリ非フォーカス時のキーボード/マウス活動をWorldへ反映する必要がある。一方で、Raw Keyboard Event、実入力文字列、キー入力列、マウス絶対座標、Window Title、クリップボード、画面内容は保存してはならない。

## Decision

Windows実活動取得は `ActivityProvider` 境界の内側に閉じ込める。Providerはサニタイズ済みの `SanitizedActivityEvent` だけを返し、World SimulationへRaw Inputを渡さない。

実装はWindows Raw Inputの利用を第一候補とし、取得した入力は即時にカテゴリ、移動量、クリック、スクロールへ変換する。Low-Level Hookは既定方針にしない。

`WM_INPUT` を処理した後は `DefWindowProcW` を呼び、Windows側のRaw Input cleanupを実行させる。

Windows API用の `ctypes.Structure` とWinAPI `argtypes` 設定は、pollや入力イベント処理のたびに作り直さず、再利用する。安定性検証ログのメモリ取得処理も同じ方針とし、診断機能自体が長時間稼働時のメモリ増加要因にならないようにする。

## Consequences

- 入力取得方式が変わっても、World側の契約は `SanitizedActivityEvent` のまま維持できる。
- Windows実機での確認が必要になる。
- アンチチート搭載ゲームとの互換性保証は `v0.8.0` の非スコープに残る。
- Raw Inputの長期保持、ログ出力、永続保存は禁止される。
