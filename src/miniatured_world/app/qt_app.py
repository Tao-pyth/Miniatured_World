from __future__ import annotations

from pathlib import Path

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.qt_widgets import build_main_window


def run_qt_app(seed: int, data_root: Path | None = None) -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    runtime = AppRuntime.start(seed=seed, provider=DemoActivityProvider(), data_root=data_root)
    window = build_main_window(runtime)
    window.show()
    return app.exec()
