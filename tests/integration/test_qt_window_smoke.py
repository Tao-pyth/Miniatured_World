import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PySide6 = pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QSlider, QTabWidget

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.app.commands import RuntimeCommand
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_main_window_contains_world_settings_and_discovery_tabs() -> None:
    _app()
    runtime = AppRuntime.start(seed=20260825, provider=DemoActivityProvider())
    window = build_main_window(runtime)
    window.show()

    try:
        tabs = window.findChild(QTabWidget)
        assert tabs is not None
        assert [tabs.tabText(index) for index in range(tabs.count())] == ["ワールド", "設定", "発見"]
        assert window.windowTitle() == "Miniatured World"
    finally:
        window.close()


def test_main_window_refreshes_from_snapshot_and_keeps_privacy_toggles_safe() -> None:
    _app()
    runtime = AppRuntime.start(seed=20260825, provider=DemoActivityProvider())
    window = build_main_window(runtime)

    try:
        snapshot = runtime.tick()
        window.refresh(snapshot)

        checkboxes = window.findChildren(QCheckBox)
        disabled_unchecked = [box for box in checkboxes if not box.isEnabled() and not box.isChecked()]
        assert len(disabled_unchecked) >= 5
        assert window.world_tab.status._value.text() == "稼働中"
        assert window.world_tab.provider._value.text() == "デモ"
    finally:
        window.close()


def test_settings_controls_update_runtime_and_persist(tmp_path) -> None:
    _app()
    runtime = AppRuntime.start(seed=20260825, provider=DemoActivityProvider(), data_root=tmp_path)
    window = build_main_window(runtime)

    try:
        checkbox = window.findChild(QCheckBox, "activity_enabled")
        assert checkbox is not None
        checkbox.setChecked(False)

        assert runtime.snapshot().activity_collection_enabled is False
        assert runtime.service.store is not None
        assert runtime.service.store.load_settings().activity.enabled is False
    finally:
        window.close()


def test_display_settings_apply_window_attributes(tmp_path) -> None:
    _app()
    runtime = AppRuntime.start(seed=20260825, provider=DemoActivityProvider(), data_root=tmp_path)
    window = build_main_window(runtime)
    window.show()

    try:
        runtime.update_setting("display", "view_mode", "desktop")
        runtime.update_setting("display", "click_through", True)
        runtime.update_setting("display", "opacity", 0.65)
        window.refresh(runtime.snapshot())

        assert bool(window.windowFlags() & Qt.WindowType.FramelessWindowHint)
        assert bool(window.windowFlags() & Qt.WindowType.Tool)
        assert bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) is True
        assert window.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is True
        assert round(window.windowOpacity(), 2) == 0.65

        runtime.update_setting("display", "view_mode", "window")
        window.refresh(runtime.snapshot())

        assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) is False
        assert window.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is False
    finally:
        window.close()


def test_display_settings_controls_update_runtime_and_window(tmp_path) -> None:
    _app()
    runtime = AppRuntime.start(seed=20260825, provider=DemoActivityProvider(), data_root=tmp_path)
    window = build_main_window(runtime)

    try:
        combo = window.findChild(QComboBox, "display_view_mode")
        assert combo is not None
        combo.setCurrentText("desktop")

        always_on_top = window.findChild(QCheckBox, "display_always_on_top")
        assert always_on_top is not None
        always_on_top.setChecked(True)

        opacity = window.findChild(QSlider, "display_opacity")
        assert opacity is not None
        opacity.setValue(70)

        window.refresh(runtime.snapshot())

        assert runtime.service.store is not None
        settings = runtime.service.store.load_settings()
        assert settings.display.view_mode == "desktop"
        assert settings.display.always_on_top is True
        assert settings.display.opacity == 0.7
        assert bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        assert round(window.windowOpacity(), 2) == 0.7
    finally:
        window.close()



def test_window_controls_use_runtime_commands_without_closing_window_on_hide() -> None:
    _app()
    runtime = AppRuntime.start(seed=20260825, provider=DemoActivityProvider())
    window = build_main_window(runtime)
    window.show()

    try:
        window.world_tab._runtime.handle(RuntimeCommand.HIDE_WORLD)
        window.refresh(runtime.snapshot())
        assert runtime.snapshot().world_visible is False
        assert window.isHidden() is False
        assert window.world_tab.preview.isHidden() is True
    finally:
        window.close()
