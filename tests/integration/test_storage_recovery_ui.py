import os
import subprocess
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from miniatured_world.app.activity_startup import prepare_activity_startup
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime


@pytest.mark.parametrize("names", [("settings.json",), ("discovery.json",), ("settings.json", "discovery.json")])
def test_recovery_notice_is_nonmodal_and_contains_no_file_contents(tmp_path, names):
    app = QApplication.instance() or QApplication([])
    for name in names:
        (tmp_path / name).write_bytes(b'{"private-file-content":')
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    window = build_main_window(runtime)
    window.show()
    try:
        app.processEvents()
        assert app.activeModalWidget() is None
        assert window.storage_notice.isVisible()
        assert "private-file-content" not in window.storage_notice.text()
        assert "保存されません" in window.storage_notice.text()
        if "settings.json" in names:
            assert "設定" in window.storage_notice.text()
        if "discovery.json" in names:
            assert "発見データ" in window.storage_notice.text()
        window.advance()
        assert runtime.snapshot().world_time > 0
        assert all((tmp_path / name).read_bytes() == b'{"private-file-content":' for name in names)
    finally:
        runtime.stop()
        window.shutdown()


def test_corrupt_settings_require_activity_choice_before_native_provider(tmp_path):
    (tmp_path / "settings.json").write_bytes(b'{')
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    made = []

    def choose():
        assert not runtime.state.activity_collection_enabled
        assert not made
        return "disable"

    assert prepare_activity_startup(runtime, "auto", lambda: made.append(True), choose)
    runtime.tick()
    assert made == []
    assert (tmp_path / "settings.json").read_bytes() == b'{'


def test_cli_reports_recovery_once_without_private_contents(tmp_path):
    (tmp_path / "settings.json").write_bytes(b'{"private-file-content":')
    result = subprocess.run([sys.executable, "-m", "miniatured_world", "--no-ui", "--activity-provider", "none",
                             "--data-root", str(tmp_path), "--frames", "3"], capture_output=True, encoding="utf-8", check=True)
    assert result.stderr.count("保存されません") == 1
    assert "private-file-content" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert (tmp_path / "settings.json").read_bytes() == b'{"private-file-content":'
