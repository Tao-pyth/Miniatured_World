import json
import os
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QPushButton, QMessageBox

from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.startup import OWNER_KEY, RUN_KEY, StartupManager


@pytest.fixture
def gui(tmp_path):
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    runtime = AppRuntime.start(1, data_root=tmp_path)
    # 旧版ではチェック値のみ保存されていた。起動の明示操作とみなさない。
    runtime.update_setting("general", "launch_on_login", True)
    values = {}
    registry = Mock()
    registry.read.side_effect = lambda key, name: values.get((key, name))
    registry.write.side_effect = lambda key, name, value: values.__setitem__((key, name), value)
    registry.delete.side_effect = lambda key, name: values.pop((key, name), None)
    runtime.startup = StartupManager(tmp_path, registry=registry, command_builder=lambda root: "lab.exe --data-root fixture")
    window = build_main_window(runtime, on_exit=Mock())
    window.show()
    app.processEvents()
    yield app, runtime, window, registry, values
    window.shutdown()
    window.deleteLater()
    app.processEvents()


def test_old_true_setting_does_not_register_until_explicit_click(gui):
    app, runtime, window, registry, values = gui
    launch = window.findChild(QCheckBox, "general_launch_on_login")
    assert not launch.isChecked()
    registry.write.assert_not_called()
    launch.click()
    assert launch.isChecked() and runtime.service.settings.general.launch_on_login
    assert (RUN_KEY, runtime.startup.name) in values
    launch.click()
    assert not launch.isChecked() and not runtime.service.settings.general.launch_on_login
    assert not values


def test_registration_failure_shows_real_disabled_state(gui):
    app, runtime, window, registry, values = gui
    registry.write.side_effect = PermissionError("private fixture marker")
    launch = window.findChild(QCheckBox, "general_launch_on_login")
    launch.click()
    assert not launch.isChecked() and launch.isEnabled()
    text = window.findChild(QLabel, "startup_status").text()
    assert "完了できません" in text and "private fixture" not in text


def test_unknown_state_is_indeterminate_and_can_be_refreshed(gui):
    app, runtime, window, registry, values = gui
    registry.read.side_effect = PermissionError()
    refresh = window.findChild(QPushButton, "startup_refresh")
    refresh.click()
    launch = window.findChild(QCheckBox, "general_launch_on_login")
    assert launch.checkState() == Qt.CheckState.PartiallyChecked
    assert not launch.isEnabled()
    registry.read.side_effect = lambda key, name: values.get((key, name))
    refresh.click()
    assert launch.checkState() == Qt.CheckState.Unchecked and launch.isEnabled()


def test_registration_works_with_settings_saving_off(gui):
    app, runtime, window, registry, values = gui
    runtime.update_setting("data", "save_settings", False)
    window.findChild(QCheckBox, "general_launch_on_login").click()
    assert runtime.startup.inspect().registered
    assert not runtime.service.settings.data.save_settings


@pytest.mark.parametrize("target", ["settings", "settings_and_discovery"])
def test_settings_deletion_removes_owned_registration(gui, tmp_path, target):
    app, runtime, window, registry, values = gui
    assert runtime.set_launch_on_login(True).succeeded
    result = runtime.delete_saved_data(target)
    assert result["startup"] and result["settings.json"]
    assert not values
    assert not (tmp_path / "settings.json").exists()
    assert not runtime.state.activity_collection_enabled


def test_failed_unregister_keeps_settings_but_deletes_discovery(gui, tmp_path):
    app, runtime, window, registry, values = gui
    runtime.tick(elapsed_ms=1000)
    assert runtime.set_launch_on_login(True).succeeded
    registry.delete.side_effect = PermissionError()
    result = runtime.delete_saved_data("settings_and_discovery")
    assert result == {"startup": False, "settings.json": False, "discovery.json": True}
    assert (tmp_path / "settings.json").exists() and not (tmp_path / "discovery.json").exists()
    assert runtime.service.settings.general.launch_on_login
    assert not runtime.service.settings.data.save_discovery
    assert runtime.startup.inspect().registered


def test_discovery_deletion_does_not_touch_startup(gui):
    app, runtime, window, registry, values = gui
    runtime.set_launch_on_login(True)
    before = dict(values)
    registry.reset_mock()
    runtime.delete_saved_data("discovery")
    assert values == before and not registry.mock_calls


def test_ephemeral_checkbox_explains_no_registration(tmp_path):
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(1)
    registry = Mock()
    runtime.startup = StartupManager(None, registry=registry)
    window = build_main_window(runtime, on_exit=Mock())
    try:
        launch = window.findChild(QCheckBox, "general_launch_on_login")
        assert not launch.isEnabled() and not launch.isChecked()
        assert "一時実行" in window.findChild(QLabel, "startup_status").text()
        assert not registry.mock_calls
    finally:
        window.shutdown()
        window.deleteLater()


@pytest.mark.parametrize("target", ["settings", "settings_and_discovery", "all"])
@pytest.mark.parametrize("confirm", [False, True])
def test_confirmed_ui_deletion_and_cancel_include_registration(gui, tmp_path, target, confirm):
    app, runtime, window, registry, values = gui
    window.timer.stop()
    window.geometry_timer.stop()
    runtime.set_launch_on_login(True)
    before = dict(values)
    seen = []

    def answer():
        dialog = window.findChild(QMessageBox, "data_delete_confirmation")
        seen.append(dialog.text())
        assert dialog.defaultButton().text() == "キャンセル"
        next(button for button in dialog.buttons() if button.text() == ("削除する" if confirm else "キャンセル")).click()

    QTimer.singleShot(0, answer)
    window.findChild(QPushButton, f"delete_{target}").click()
    assert "起動登録も解除" in seen[0]
    if confirm:
        assert not values and not (tmp_path / "settings.json").exists()
        assert "起動登録を解除しました" in window.data_result.text()
        assert not window.settings_tab.findChild(QCheckBox, "general_launch_on_login").isChecked()
    else:
        assert values == before and not window.data_result.text()


def test_all_ui_reports_failed_unregistration_and_successful_sibling_deletion(gui, tmp_path):
    app, runtime, window, registry, values = gui
    window.timer.stop()
    runtime.tick(elapsed_ms=1000)
    runtime.set_launch_on_login(True)
    registry.delete.side_effect = PermissionError()

    def answer():
        dialog = window.findChild(QMessageBox, "data_delete_confirmation")
        next(button for button in dialog.buttons() if button.text() == "削除する").click()

    QTimer.singleShot(0, answer)
    window.findChild(QPushButton, "delete_all").click()
    assert (tmp_path / "settings.json").exists()
    assert not (tmp_path / "discovery.json").exists()
    result = "\n".join(window._data_result_lines)
    assert "起動登録を解除できません" in result and "発見データを削除しました" in result
    assert window.settings_tab.findChild(QCheckBox, "general_launch_on_login").isChecked()
