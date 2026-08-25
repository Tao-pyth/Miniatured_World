from __future__ import annotations

import argparse
import sys
from pathlib import Path

from miniatured_world.activity import create_activity_provider
from miniatured_world.app.runtime import AppRuntime
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
    parser = _JapaneseArgumentParser(prog="miniatured-world", description="Miniatured World を起動します。", add_help=False)
    parser.add_argument("-h", "--help", action="help", help="このヘルプを表示して終了します。")
    parser.add_argument("--seed", type=int, default=20260825, help="ワールド生成に使うシード値。")
    parser.add_argument("--frames", type=int, default=5, help="UIなし実行で進めるフレーム数。")
    parser.add_argument("--no-ui", action="store_true", help="Qt画面を起動せず、CLIでスモーク実行します。")
    parser.add_argument("--data-root", type=Path, default=None, help="設定と発見情報を保存するディレクトリ。")
    parser.add_argument("--ephemeral", action="store_true", help="設定と発見情報を保存しない一時実行にします。")
    parser.add_argument(
        "--activity-provider",
        choices=("auto", "demo", "none", "windows-idle"),
        default="auto",
        help="活動取得元を選択します。",
    )
    args = parser.parse_args(argv)
    data_root = None if args.ephemeral else args.data_root or default_data_root()
    provider = create_activity_provider(args.activity_provider)

    if not args.no_ui:
        try:
            from miniatured_world.app.qt_app import run_qt_app

            return run_qt_app(seed=args.seed, data_root=data_root, provider=provider)
        except ImportError:
            pass

    runtime = AppRuntime.start(seed=args.seed, provider=provider, data_root=data_root)
    for _ in range(args.frames):
        runtime.tick()

    print(runtime.service.summary_text())
    return 0


def _configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
