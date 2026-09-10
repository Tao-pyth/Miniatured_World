import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.app.qt_session import create_session_monitor, WM_WTSSESSION_CHANGE, WM_POWERBROADCAST
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.windows_session import SessionState


class FakeAPI:
    session_id = 7
    registered = True
    state = SessionState(False, False)

    def __init__(self):
        self.removed = []

    def register(self, hwnd):
        return self.registered

    def unregister(self, hwnd):
        self.removed.append(hwnd)

    def query(self):
        return self.state


@pytest.fixture
def gui():
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(seed=42, provider=DemoActivityProvider())
    window = build_main_window(runtime, tick_interval_ms=25)
    api = FakeAPI()
    monitor = create_session_monitor(runtime, window.refresh, api=api)
    window.show()
    QTest.qWait(80)
    yield runtime, window, monitor, api
    monitor.stop()
    runtime.stop()
    window.close()
    window.deleteLater()
    app.processEvents()


@pytest.mark.parametrize("manual", [False, True])
def test_lock_freezes_world_and_animation_then_restores_manual_state(gui, manual):
    runtime, window, monitor, api = gui
    runtime.state.paused = manual
    before = runtime.snapshot().world_time
    monitor.handle_message(WM_WTSSESSION_CHANGE, 7, api.session_id)
    QTest.qWait(100)
    assert runtime.snapshot().world_time == before
    assert not window.world_tab.preview.animation_timer.isActive()
    assert window.world_tab.pause_button.text() == ("再開" if manual else "一時停止")
    monitor.handle_message(WM_WTSSESSION_CHANGE, 8, api.session_id)
    QTest.qWait(100)
    assert runtime.state.paused == manual
    assert (runtime.snapshot().world_time == before) == manual


def test_other_session_ignored_and_sleep_lock_overlap(gui):
    runtime, window, monitor, api = gui
    monitor.handle_message(WM_WTSSESSION_CHANGE, 7, 99)
    assert not runtime.snapshot().system_paused
    api.state = SessionState(True, False)
    monitor.handle_message(WM_WTSSESSION_CHANGE, 7, 7)
    monitor.handle_message(WM_POWERBROADCAST, 4, 0)
    monitor.handle_message(WM_POWERBROADCAST, 18, 0)
    assert runtime.snapshot().system_paused
    monitor.handle_message(WM_WTSSESSION_CHANGE, 8, 7)
    assert not runtime.snapshot().system_paused


def test_monitor_survives_window_close_hide_and_display_mode(gui):
    runtime, window, monitor, api = gui
    hwnd = monitor._handle
    window.close()
    monitor.handle_message(WM_WTSSESSION_CHANGE, 7, 7)
    window.showNormal()
    before = runtime.snapshot().world_time
    runtime.update_setting("display", "view_mode", "desktop")
    window.refresh(runtime.snapshot())
    QTest.qWait(80)
    assert monitor._handle == hwnd
    assert runtime.snapshot().world_time == before
    assert not window.world_tab.preview.animation_timer.isActive()
    monitor.handle_message(WM_WTSSESSION_CHANGE, 8, 7)
    window.hide()
    QTest.qWait(80)
    assert runtime.snapshot().world_time > before
    assert api.removed == []


def test_unknown_state_retries_and_stopped_monitor_unregisters_once(gui):
    runtime, window, monitor, api = gui
    api.state = None
    monitor.synchronize()
    assert runtime.snapshot().system_paused
    assert "再試行" in window.world_tab.status.toolTip()
    api.state = SessionState(True, False)
    monitor.synchronize()
    assert runtime.state.system_pause_reasons == {"session_locked"}
    api.state = SessionState(False, False)
    monitor.synchronize()
    assert not runtime.snapshot().system_paused
    monitor.stop()
    monitor.stop()
    monitor.handle_message(WM_WTSSESSION_CHANGE, 7, 7)
    assert not runtime.snapshot().system_paused
    assert len(api.removed) == 1


@pytest.mark.parametrize("registered,state", [(False, SessionState(False, False)), (True, SessionState(True, False))])
def test_initial_registration_failure_or_lock_pauses_before_tick(registered, state):
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(seed=42)
    api = FakeAPI()
    api.registered, api.state = registered, state
    monitor = create_session_monitor(runtime, lambda snapshot: None, api=api)
    try:
        assert runtime.tick().world_time == 0
        assert runtime.snapshot().system_paused
        api.registered, api.state = True, SessionState(False, False)
        monitor.synchronize()
        assert runtime.tick().world_time > 0
    finally:
        monitor.stop()
        app.processEvents()
