import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.app.qt_tray import attach_tray
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate()


@pytest.mark.parametrize("paused,activity,visible", [
    (False, True, True), (True, True, True),
    (False, False, True), (False, True, False),
])
def test_reopen_resumes_same_session_and_preserves_controls(paused, activity, visible, monkeypatch):
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(seed=42, provider=DemoActivityProvider())
    window = build_main_window(runtime, tick_interval_ms=25)
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    attach_tray(app, window, runtime)
    try:
        window.show()
        _wait_until(lambda: runtime.snapshot().world_time > 0)
        runtime.state.paused = paused
        runtime.set_activity_collection(activity)
        runtime.state.world_visible = visible
        window.refresh(runtime.snapshot())
        simulation = runtime.service.simulation
        for _ in range(2):
            window.close()
            before = runtime.snapshot().world_time
            QTest.qWait(60)
            assert window.timer.isActive()
            if paused:
                assert runtime.snapshot().world_time == before
            else:
                _wait_until(lambda: runtime.snapshot().world_time > before)
            window.showNormal()
            assert window.timer.isActive()
            assert window.timer.interval() == 25
            assert runtime.service.simulation is simulation
            assert runtime.snapshot().seed == 42
            assert runtime.state.paused is paused
            assert runtime.state.activity_collection_enabled is activity
            assert runtime.state.world_visible is visible
            if paused:
                QTest.qWait(75)
                assert runtime.snapshot().world_time == before
            else:
                _wait_until(lambda: runtime.snapshot().world_time > before)
        if paused:
            runtime.resume()
            _wait_until(lambda: runtime.snapshot().world_time > before)
    finally:
        runtime.stop()
        window.shutdown()
        window.deleteLater()
        app.processEvents()


@pytest.mark.parametrize("entry", ["show", "settings", "discovery", "activation"])
def test_all_tray_reopen_entries_restart_world(entry, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    runtime = AppRuntime.start(seed=42, provider=DemoActivityProvider())
    window = build_main_window(runtime, tick_interval_ms=25)
    tray = attach_tray(app, window, runtime)
    try:
        window.show()
        _wait_until(lambda: runtime.snapshot().world_time > 0)
        window.close()
        before = runtime.snapshot().world_time
        if entry == "activation":
            tray.activated.emit(QSystemTrayIcon.ActivationReason.Trigger)
        else:
            tray._miniatured_world_actions[entry].trigger()
        assert window.isVisible()
        _wait_until(lambda: runtime.snapshot().world_time > before)
        expected_tab = {"settings": "設定", "discovery": "発見"}.get(entry, "ラボ")
        assert window.tabs.tabText(window.tabs.currentIndex()) == expected_tab
    finally:
        tray.hide()
        runtime.stop()
        window.shutdown()
        window.deleteLater()
        app.processEvents()


@pytest.mark.parametrize("completed", [False, True])
def test_reopen_does_not_restart_stopped_or_completed_session(completed):
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(seed=42, provider=DemoActivityProvider())
    window = build_main_window(runtime, duration_seconds=0.05 if completed else None, tick_interval_ms=25)
    try:
        window.show()
        if completed:
            _wait_until(lambda: not runtime.state.running)
        else:
            runtime.stop()
            window.close()
        before = runtime.snapshot().world_time
        window.showNormal()
        QTest.qWait(75)
        assert not window.timer.isActive()
        assert runtime.snapshot().world_time == before
        assert not window.world_tab.preview.animation_timer.isActive()
    finally:
        window.shutdown()
        window.deleteLater()
        app.processEvents()


def test_tray_reopen_keeps_diagnostic_log_running(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(seed=42, provider=DemoActivityProvider())
    log = tmp_path / "stability.jsonl"
    window = build_main_window(runtime, duration_seconds=100, tick_interval_ms=25, stability_log=log)
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    attach_tray(app, window, runtime)
    try:
        window.show()
        _wait_until(lambda: runtime.snapshot().world_time > 0)
        window.close()
        contents = log.read_bytes()
        assert not window._stability_logger.closed
        assert json.loads(contents.decode().splitlines()[-1])["event"] == "tick"
        before = runtime.snapshot().world_time
        window.showNormal()
        _wait_until(lambda: runtime.snapshot().world_time > before)
        assert len(log.read_bytes()) > len(contents)
        assert not any(json.loads(line)["event"] == "cancelled" for line in log.read_text(encoding="utf-8").splitlines())
    finally:
        runtime.stop()
        window.shutdown()
        window.deleteLater()
        app.processEvents()


def test_hide_show_preserves_running_timer():
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(seed=42, provider=DemoActivityProvider())
    window = build_main_window(runtime, tick_interval_ms=25)
    try:
        window.show()
        timer_id = window.timer.timerId()
        window.hide()
        before = runtime.snapshot().world_time
        _wait_until(lambda: runtime.snapshot().world_time > before)
        window.showNormal()
        assert window.timer.timerId() == timer_id
    finally:
        runtime.stop()
        window.shutdown()
        window.deleteLater()
        app.processEvents()
