import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PySide6 = pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QCheckBox, QTabWidget

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
