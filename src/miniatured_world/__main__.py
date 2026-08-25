from __future__ import annotations

import argparse

from miniatured_world.app.service import MiniaturedWorldService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="miniatured-world")
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--frames", type=int, default=5)
    parser.add_argument("--no-ui", action="store_true")
    args = parser.parse_args(argv)

    if not args.no_ui:
        try:
            from miniatured_world.app.qt_app import run_qt_app

            return run_qt_app(seed=args.seed)
        except ImportError:
            pass

    service = MiniaturedWorldService.start(seed=args.seed)
    for frame_index in range(args.frames):
        service.inject_demo_activity(frame_index)
        service.step()

    print(service.summary_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

