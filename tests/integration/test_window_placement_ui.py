import os
import time
from dataclasses import replace
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtTest import QTest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.persistence.settings import WindowSettings
from miniatured_world.persistence.settings import Settings
from miniatured_world.persistence.store import JsonStore


@pytest.fixture
def gui(tmp_path):
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    windows = []

    def start():
        runtime = AppRuntime.start(1, data_root=tmp_path)
        window = build_main_window(runtime, on_exit=Mock())
        windows.append(window)
        window.show()
        app.processEvents()
        window._fit_placement(WindowSettings(True, 0, 20, 940, 660))
        return runtime, window

    yield app, start
    for window in windows:
        window.shutdown()
        window.deleteLater()
    app.processEvents()


def test_shutdown_flushes_and_restart_restores_normal_geometry(gui, tmp_path):
    app, start = gui
    runtime, window = start()
    expected = window._read_placement()
    window.shutdown()
    assert JsonStore(tmp_path).load_settings().window == expected
    restarted = AppRuntime.start(2, data_root=tmp_path)
    restored = build_main_window(restarted, on_exit=Mock())
    try:
        restored.show()
        app.processEvents()
        assert restored._read_placement() == expected
    finally:
        restored.shutdown()
        restored.deleteLater()


def test_moves_are_coalesced_and_latest_is_saved(gui, monkeypatch):
    app, start = gui
    runtime, window = start()
    calls = []
    original = type(runtime.service).remember_window

    def observe(service, placement):
        calls.append(placement)
        original(service, placement)

    monkeypatch.setattr(type(runtime.service), "remember_window", observe)
    for y in range(21, 31):
        window.move(window.x(), y)
    assert not calls
    deadline = time.monotonic() + 2
    while not calls and time.monotonic() < deadline:
        QTest.qWait(10)
    assert calls == [window._read_placement()]


@pytest.mark.parametrize("state", ["maximized", "minimized", "desktop"])
def test_non_normal_state_keeps_normal_placement(gui, tmp_path, state):
    app, start = gui
    runtime, window = start()
    window._save_window_placement()
    expected = runtime.service.settings.window
    if state == "desktop":
        runtime.update_setting("display", "view_mode", "desktop")
        window.refresh(runtime.snapshot())
        window.move(300, 300)
        window.resize(1200, 800)
    elif state == "maximized":
        window.showMaximized()
    else:
        window.showMinimized()
    app.processEvents()
    window.shutdown()
    assert JsonStore(tmp_path).load_settings().window == expected


def test_desktop_return_restores_normal_position(gui):
    app, start = gui
    runtime, window = start()
    expected = window._read_placement()
    runtime.update_setting("display", "view_mode", "desktop")
    window.refresh(runtime.snapshot())
    window.move(300, 300)
    runtime.update_setting("display", "view_mode", "window")
    window.refresh(runtime.snapshot())
    app.processEvents()
    assert window._read_placement() == expected


def test_starting_in_desktop_mode_keeps_last_normal_position(tmp_path):
    app = QApplication.instance() or QApplication([])
    settings = Settings(window=WindowSettings(True, 0, 20, 940, 660))
    settings = replace(settings, display=replace(settings.display, view_mode="desktop"))
    JsonStore(tmp_path).save_settings(settings)
    runtime = AppRuntime.start(1, data_root=tmp_path)
    window = build_main_window(runtime, on_exit=Mock())
    try:
        window.show()
        app.processEvents()
        window.move(300, 300)
        runtime.update_setting("display", "view_mode", "window")
        window.refresh(runtime.snapshot())
        app.processEvents()
        assert window._read_placement().y == 20
    finally:
        window.shutdown()
        window.deleteLater()


def test_pending_move_cannot_recreate_deleted_settings(gui, tmp_path):
    app, start = gui
    runtime, window = start()
    window.move(window.x(), 31)
    assert runtime.delete_saved_data("settings")["settings.json"]
    window.shutdown()
    assert not (tmp_path / "settings.json").exists()


def test_hidden_to_tray_flushes_without_ending_runtime(gui, monkeypatch, tmp_path):
    app, start = gui
    runtime, window = start()
    monkeypatch.setattr(window, "_tray_available", lambda: True)
    expected = window._read_placement()
    window.hide_to_tray()
    assert JsonStore(tmp_path).load_settings().window == expected
    assert runtime.state.running and not window.isVisible()
    window.showNormal()
    app.processEvents()
    assert window._read_placement() == expected


def test_small_available_area_keeps_window_and_controls_accessible(gui, monkeypatch):
    app, start = gui
    runtime, window = start()
    screen = Mock()
    area = QRect(40, 40, 640, 450)
    screen.availableGeometry.return_value = area
    monkeypatch.setattr(QApplication, "screens", staticmethod(lambda: [screen]))
    monkeypatch.setattr(QApplication, "primaryScreen", staticmethod(lambda: screen))
    window._fit_placement(WindowSettings(True, 5000, 5000, 9000, 7000))
    app.processEvents()
    assert area.contains(window.frameGeometry())
    window.tabs.setCurrentIndex(1)
    app.processEvents()
    assert window.content_scroll.widget() is window.tabs
    assert window.content_scroll.horizontalScrollBar().maximum() > 0 or window.content_scroll.verticalScrollBar().maximum() > 0
    from PySide6.QtWidgets import QCheckBox
    preference = window.settings_tab.findChild(QCheckBox, "general_restore_window_position")
    assert preference is not None
    window.content_scroll.ensureWidgetVisible(preference)
    assert preference.isEnabled()
    viewport = window.content_scroll.viewport()
    assert viewport.rect().contains(preference.mapTo(viewport, preference.rect().center()))
    preference.click()
    assert not runtime.service.settings.general.restore_window_position


@pytest.mark.parametrize("section,field", [("data", "save_settings"), ("general", "restore_window_position")])
def test_switch_off_before_debounce_does_not_save_moved_position(gui, tmp_path, section, field):
    app, start = gui
    runtime, window = start()
    window._save_window_placement()
    old = runtime.service.settings.window
    window.move(window.x(), 35)
    runtime.update_setting(section, field, False)
    original = (tmp_path / "settings.json").read_bytes()
    window.shutdown()
    assert (tmp_path / "settings.json").read_bytes() == original
    assert JsonStore(tmp_path).load_settings().window == old
