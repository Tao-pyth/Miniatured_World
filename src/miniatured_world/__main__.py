from __future__ import annotations

import argparse
import sys
from pathlib import Path

from miniatured_world.activity import create_activity_provider
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.stability import run_stability_check
from miniatured_world.persistence import default_data_root


class _JapaneseArgumentParser(argparse.ArgumentParser):
    def format_usage(self) -> str:
        return super().format_usage().replace("usage:", "使い方:")

    def format_help(self) -> str:
        return (
            super()
            .format_help()
            .replace("usage:", "使い方:")
            .replace("options:", "オプション:")
        )


def main(argv: list[str] | None = None) -> int:
    _configure_console_output()
    parser = _JapaneseArgumentParser(prog="miniatured-world", description="小さなラボラトリーを起動します。", add_help=False)
    parser.add_argument("-h", "--help", action="help", help="このヘルプを表示して終了します。")
    parser.add_argument("--seed", type=int, default=20260825, help="ラボのセッション生成に使うシード値。")
    parser.add_argument("--frames", type=int, default=5, help="UIなし実行で進めるフレーム数。")
    parser.add_argument("--duration-seconds", type=float, default=None, help="安定性検証で実行する秒数。")
    parser.add_argument("--tick-interval-ms", type=int, default=1000, help="1フレームの経過時間ミリ秒。")
    parser.add_argument("--realtime", action="store_true", help="安定性検証を壁時計の経過に合わせて実行します。")
    parser.add_argument("--stability-log", type=Path, default=None, help="安定性検証ログをJSONL形式で保存するパス。")
    parser.add_argument("--no-ui", action="store_true", help="Qt画面を起動せず、CLIでスモーク実行します。")
    parser.add_argument("--data-root", type=Path, default=None, help="設定と発見情報を保存するディレクトリ。")
    parser.add_argument("--ephemeral", action="store_true", help="設定と発見情報を保存しない一時実行にします。")
    parser.add_argument(
        "--activity-provider",
        choices=("auto", "demo", "none", "windows-idle", "windows-global"),
        default="auto",
        help="活動取得元を選択します。windows-global はWindows実活動取得を試みます。",
    )
    args = parser.parse_args(argv)
    data_root = None if args.ephemeral else args.data_root or default_data_root()
    provider = create_activity_provider(args.activity_provider)

    if not args.no_ui:
        try:
            from miniatured_world.app.qt_app import run_qt_app

            duration_seconds = args.duration_seconds
            if args.stability_log and duration_seconds is None:
                duration_seconds = max(1, args.frames) * args.tick_interval_ms / 1000
            return run_qt_app(
                seed=args.seed,
                data_root=data_root,
                provider=provider,
                duration_seconds=duration_seconds,
                tick_interval_ms=args.tick_interval_ms,
                stability_log=args.stability_log,
            )
        except ImportError as error:
            print(f"Qt画面を起動できないためCLI実行へ切り替えます: {error}", file=sys.stderr)

    runtime = AppRuntime.start(seed=args.seed, provider=provider, data_root=data_root)
    if args.stability_log:
        duration_seconds = args.duration_seconds
        if duration_seconds is None:
            duration_seconds = max(1, args.frames) * args.tick_interval_ms / 1000
        run_stability_check(
            runtime,
            log_path=args.stability_log,
            duration_seconds=duration_seconds,
            tick_interval_ms=args.tick_interval_ms,
            realtime=args.realtime,
        )
        print(runtime.service.summary_text())
        print(f"安定性ログ={args.stability_log}")
        return 0

    for _ in range(args.frames):
        runtime.tick(elapsed_ms=args.tick_interval_ms)

    print(runtime.service.summary_text())
    return 0


def _configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
