import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.app.qt_tray import attach_tray
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime


def wait_until(predicate):
    deadline = time.monotonic() + 2.0
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate()


@pytest.fixture
def gui(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    runtime = AppRuntime.start(42, provider=DemoActivityProvider(), data_root=tmp_path / "data")
    runtime.update_setting("general", "minimize_to_tray", False)
    quit_app = Mock()
    window = build_main_window(runtime, stability_log=tmp_path / "run.jsonl", on_exit=quit_app)
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    attach_tray(app, window, runtime)
    window.show()
    app.processEvents()
    yield app, runtime, window, quit_app
    window.shutdown()
    window.deleteLater()
    app.processEvents()


def trigger(window, route):
    if route == "lab":
        window.world_tab.exit_button.click()
    elif route == "tray":
        window.tray._miniatured_world_actions["exit"].trigger()
    else:
        window.close()


@pytest.mark.parametrize("route", ["lab", "tray", "close"])
@pytest.mark.parametrize("answer", ["cancel", "escape", "close", "confirm"])
def test_confirmation_and_cancel_preserve_running_session(gui, route, answer):
    app, runtime, window, quit_app = gui
    simulation = runtime.service.simulation
    before = runtime.snapshot().world_time
    observed = []

    def respond():
        dialog = window._exit_dialog
        observed.append((dialog.defaultButton().text(), runtime.state.running, window.timer.isActive()))
        # 確認待ちでも同じWorldとログが継続する。
        window.advance()
        if answer == "escape":
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
        elif answer == "close":
            dialog.close()
        else:
            next(b for b in dialog.buttons() if b.text() == ("終了する" if answer == "confirm" else "キャンセル")).click()

    QTimer.singleShot(10, respond)
    trigger(window, route)
    wait_until(lambda: window._exit_dialog is None)
    assert observed == [("キャンセル", True, True)]
    assert runtime.service.simulation is simulation
    assert runtime.snapshot().seed == 42
    assert runtime.snapshot().world_time > before
    if answer == "confirm":
        assert not runtime.state.running
        assert not window.isVisible() and not window.tray.isVisible()
        assert not window.timer.isActive() and not window.world_tab.preview.animation_timer.isActive()
        assert window._stability_logger.closed
        quit_app.assert_called_once()
    else:
        assert runtime.state.running and window.isVisible()
        assert window.timer.isActive() and not window._stability_logger.closed
        quit_app.assert_not_called()


@pytest.mark.parametrize("route", ["lab", "tray", "close"])
def test_confirmation_disabled_and_shutdown_idempotent(gui, route, monkeypatch):
    app, runtime, window, quit_app = gui
    runtime.update_setting("general", "confirm_on_exit", False)
    retry = Mock(wraps=runtime.service.retry_pending_saves)
    monkeypatch.setattr(type(runtime.service), "retry_pending_saves", retry)
    modal = Mock(side_effect=AssertionError("disabled confirmation opened"))
    monkeypatch.setattr(QMessageBox, "show", modal)
    trigger(window, route)
    window.shutdown()
    window.request_exit()
    window.advance()
    assert not runtime.state.running
    quit_app.assert_called_once()
    retry.assert_called_once_with(force=True)
    rows = [json.loads(s) for s in window._stability_logger.log_path.read_text(encoding="utf-8").splitlines()]
    assert [row["event"] for row in rows].count("cancelled") == 1


@pytest.mark.parametrize("paused,system,activity", [(False, False, True), (True, False, True), (False, True, True), (False, False, False)])
def test_cancel_keeps_control_state_and_single_dialog(gui, paused, system, activity):
    app, runtime, window, quit_app = gui
    if paused:
        runtime.pause()
    runtime.set_system_suspended("session_locked", system)
    runtime.set_activity_collection(activity)
    window.refresh(runtime.snapshot())
    before = runtime.snapshot().world_time
    observed = []
    def respond():
        first = window._exit_dialog
        observed.append(window.request_exit())
        observed.append(window._exit_dialog is first)
        window.advance()
        first.reject()
    QTimer.singleShot(10, respond)
    window.request_exit()
    wait_until(lambda: window._exit_dialog is None)
    assert observed == [False, True]
    assert runtime.state.paused is paused
    assert bool(runtime.state.system_pause_reasons) is system
    assert runtime.state.activity_collection_enabled is activity
    assert runtime.state.running and not window._stability_logger.closed
    assert runtime.snapshot().world_time == before if paused or system else runtime.snapshot().world_time > before


def test_minimize_and_tray_loss_keep_world_accessible(gui, monkeypatch):
    app, runtime, window, quit_app = gui
    runtime.update_setting("general", "minimize_to_tray", True)
    before = runtime.snapshot().world_time
    for _ in range(2):
        window.close()
        app.processEvents()
        assert not window.isVisible()
        assert window.timer.isActive() and not window.world_tab.preview.animation_timer.isActive()
        window.advance()
        assert runtime.snapshot().world_time > before
        before = runtime.snapshot().world_time
        assert not window._stability_logger.closed
        window.tray._miniatured_world_actions["show"].trigger()
        app.processEvents()
        assert window.isVisible() and window.world_tab.preview.animation_timer.isActive()
    window.hide_to_tray()
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: False))
    window.advance()
    assert window.isVisible() and runtime.state.running
    window.hide_to_tray()
    assert window.isVisible()
    quit_app.assert_not_called()


@pytest.mark.parametrize("missing", ["absent", "hidden", "unavailable"])
def test_close_without_usable_tray_uses_confirmation(gui, missing, monkeypatch):
    app, runtime, window, quit_app = gui
    runtime.update_setting("general", "minimize_to_tray", True)
    if missing == "absent":
        window.tray.hide()
        window.tray = None
    elif missing == "hidden":
        window.tray.hide()
    else:
        monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: False))
    QTimer.singleShot(10, lambda: window._exit_dialog.reject())
    window.close()
    wait_until(lambda: window._exit_dialog is None)
    assert window.isVisible() and runtime.state.running
    quit_app.assert_not_called()


def test_session_close_is_noninteractive(gui, monkeypatch):
    app, runtime, window, quit_app = gui
    runtime.update_setting("general", "minimize_to_tray", True)
    monkeypatch.setattr(QApplication, "isSavingSession", staticmethod(lambda: True))
    monkeypatch.setattr(QMessageBox, "show", Mock(side_effect=AssertionError("session close prompted")))
    window.close()
    assert not runtime.state.running and not window.tray.isVisible()
    quit_app.assert_called_once()


def test_duration_closes_pending_confirmation(tmp_path):
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(42)
    done = Mock()
    window = build_main_window(runtime, duration_seconds=0.02, tick_interval_ms=20,
                               stability_log=tmp_path / "run.jsonl", on_stability_complete=done)
    try:
        window.show()
        window.request_exit()
        wait_until(lambda: not runtime.state.running)
        assert not runtime.state.running and window._exit_dialog is None
        assert not window.timer.isActive()
        done.assert_called_once()
        rows = [json.loads(line) for line in (tmp_path / "run.jsonl").read_text(encoding="utf-8").splitlines()]
        assert [row["event"] for row in rows] == ["start", "tick", "completed"]
    finally:
        window.shutdown()


@pytest.mark.parametrize("route", ["lab", "tray", "close", "app_quit", "runtime_exit", "duration"])
def test_real_qt_event_loop_exits_process(tmp_path, route):
    script = r'''
import sys,json
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QMessageBox,QSystemTrayIcon
from miniatured_world.app.qt_app import run_qt_app
from miniatured_world.app.commands import RuntimeCommand
app=QApplication([]);route=sys.argv[1];windows=[];prompts=[];fallback=[]
QSystemTrayIcon.isSystemTrayAvailable=staticmethod(lambda: True)
def answer():
    if not windows:return
    dialog=windows[0]._exit_dialog
    if dialog is not None:
        prompts.append(True)
        next(b for b in dialog.buttons() if b.text()=='終了する').click()
timer=QTimer();timer.timeout.connect(answer);timer.start(10)
def drive():
    w=next(w for w in app.topLevelWidgets() if hasattr(w,'world_tab'));windows.append(w)
    w.runtime.update_setting('general','minimize_to_tray',False)
    if route=='lab':w.world_tab.exit_button.click()
    elif route=='tray':w.tray._miniatured_world_actions['exit'].trigger()
    elif route=='close':w.close()
    elif route=='runtime_exit':w.runtime.handle(RuntimeCommand.EXIT)
    elif route=='app_quit':app.quit()
QTimer.singleShot(100,drive)
QTimer.singleShot(4000,lambda: (fallback.append(True),app.exit(91)))
code=run_qt_app(42,data_root=None,activity_provider='none',duration_seconds=0.3 if route=='duration' else None,tick_interval_ms=100)
assert not fallback and code==0
assert len(prompts)==(1 if route in ('lab','tray','close') else 0)
assert windows and not windows[0].runtime.state.running and not windows[0].timer.isActive()
print(json.dumps({'route':route,'exit_code':code,'prompts':len(prompts),'running':windows[0].runtime.state.running}))
'''
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    result = subprocess.run([sys.executable, "-c", script, route], env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["running"] is False
