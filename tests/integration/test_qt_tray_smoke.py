import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PySide6 = pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.app.qt_tray import attach_tray
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_tray_attachment_is_safe_when_tray_is_unavailable() -> None:
    app = _app()
    runtime = AppRuntime.start(seed=20260825, provider=DemoActivityProvider())
    window = build_main_window(runtime)

    try:
        tray = attach_tray(app, window, runtime)
        if QSystemTrayIcon.isSystemTrayAvailable():
            assert tray is not None
            assert tray.contextMenu() is not None
            assert len(tray.contextMenu().actions()) >= 10
            labels = [action.text() for action in tray.contextMenu().actions()]
            assert "設定" in labels
            assert "発見" in labels
            assert "終了" in labels
        else:
            assert tray is None
    finally:
        window.close()
