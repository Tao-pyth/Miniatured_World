"""設定画面と一時停止ボタンからネイティブ取得休止へ到達すること。"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QCheckBox

from miniatured_world.activity.windows_global import WindowsGlobalActivityProvider, _WindowsRawInputBackend
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime


def test_settings_and_pause_button_hold_backend_until_all_controls_resume():
    app = QApplication.instance() or QApplication([])
    backend = object.__new__(_WindowsRawInputBackend)
    backend._suspended = False
    backend._hwnd = None
    backend._available = True
    backend._detail = "検査用"
    backend._queue = []
    backend._poll_timestamp_ms = 1000
    backend._pump_messages = lambda: None
    runtime = AppRuntime.start(42, provider=WindowsGlobalActivityProvider(backend=backend))
    window = build_main_window(runtime)
    window.timer.stop()
    try:
        checkbox = window.findChild(QCheckBox, "activity_enabled")
        checkbox.setChecked(False)
        assert backend._suspended
        runtime.set_system_suspended("session_locked", True)
        runtime.set_system_suspended("session_locked", False)
        assert backend._suspended
        window.world_tab.pause_button.click()
        checkbox.setChecked(True)
        assert backend._suspended and runtime.state.paused
        window.world_tab.pause_button.click()
        assert not backend._suspended
        assert runtime.tick().world_time > 0
        runtime.handle("stop_activity")
        assert backend._suspended
        runtime.handle("start_activity")
        assert not backend._suspended
        runtime.stop()
        assert backend._suspended
    finally:
        window.shutdown()
        app.processEvents()
