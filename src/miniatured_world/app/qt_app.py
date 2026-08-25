from __future__ import annotations

from pathlib import Path

from miniatured_world.activity import ActivityProvider, create_activity_provider
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.qt_tray import attach_tray
from miniatured_world.persistence import default_data_root


def run_qt_app(seed: int, data_root: Path | None = None, provider: ActivityProvider | None = None) -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    runtime = AppRuntime.start(seed=seed, provider=provider or create_activity_provider("auto"), data_root=data_root or default_data_root())
    window = build_main_window(runtime)
    window.tray = attach_tray(app, window, runtime)
    window.show()
    return app.exec()
