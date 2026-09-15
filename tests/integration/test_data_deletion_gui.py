import os
from pathlib import Path
from unittest.mock import patch

import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QCheckBox, QMessageBox, QPushButton
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.qt_widgets import build_main_window


@pytest.mark.parametrize("target", ["discovery", "settings", "settings_and_discovery"])
@pytest.mark.parametrize("confirm", [False, True])
def test_real_modal_confirmation_cancel_and_state_refresh(tmp_path, target, confirm):
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(42, data_root=tmp_path)
    runtime.service.simulation.session.state.discoveries.add("old-ui-fixture")
    runtime.tick()
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    window = build_main_window(runtime)
    window.timer.stop()
    observed = []
    def answer():
        dialog = window.findChild(QMessageBox, "data_delete_confirmation")
        assert dialog.defaultButton().text() == "キャンセル"
        assert dialog.escapeButton().text() == "キャンセル"
        observed.append(dialog.text())
        next(b for b in dialog.buttons() if b.text() == ("削除する" if confirm else "キャンセル")).click()
    try:
        QTimer.singleShot(0, answer)
        window.findChild(QPushButton, f"delete_{target}").click()
        assert observed and "元に戻せません" in observed[0]
        if not confirm:
            assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
            assert "old-ui-fixture" in runtime.service.discovery_manager.discoveries
            assert not window.data_result.text()
        else:
            assert "削除しました" in window.data_result.text()
            if target != "settings":
                assert not (tmp_path / "discovery.json").exists()
                assert not window.settings_tab.findChild(QCheckBox, "data_save_discovery").isChecked()
            if target != "discovery":
                assert not (tmp_path / "settings.json").exists()
                assert not window.settings_tab.findChild(QCheckBox, "data_save_settings").isChecked()
                assert not window.settings_tab.findChild(QCheckBox, "activity_enabled").isChecked()
    finally:
        runtime.stop()
        window.shutdown()


def test_gui_partial_failure_does_not_claim_everything_deleted(tmp_path):
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(42, data_root=tmp_path)
    runtime.tick()
    window = build_main_window(runtime)
    window.timer.stop()
    original = Path.unlink
    def deny(path, *args, **kwargs):
        if path.name == "settings.json":
            raise PermissionError("secret")
        return original(path, *args, **kwargs)
    def confirm():
        dialog = window.findChild(QMessageBox)
        next(b for b in dialog.buttons() if b.text() == "削除する").click()
    try:
        QTimer.singleShot(0, confirm)
        with patch.object(Path, "unlink", deny):
            window.findChild(QPushButton, "delete_settings_and_discovery").click()
        assert "発見データを削除しました" in window.data_result.text()
        assert "設定を削除できませんでした" in window.data_result.text()
        assert "古い内容の再保存を止めています" in window.storage_notice.text()
        assert "secret" not in window.storage_notice.text()
    finally:
        runtime.stop()
        window.shutdown()


def test_ephemeral_disables_all_persistent_delete_actions():
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(42)
    window = build_main_window(runtime)
    try:
        buttons = [b for b in window.findChildren(QPushButton) if b.objectName().startswith("delete_")]
        assert len(buttons) == 7
        assert all(b.isEnabled() == (b.objectName() == "delete_cache") for b in buttons)
    finally:
        runtime.stop()
        window.shutdown()
