import os
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.persistence import JsonStore, DiscoveryRecord


def test_history_visible_but_not_reintroduced_into_world(tmp_path):
    app = QApplication.instance() or QApplication([])
    JsonStore(tmp_path).save_discovery(DiscoveryRecord(discoveries=["historic-only", "historic-only"]))
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    window = build_main_window(runtime)
    window.timer.stop()
    try:
        assert window.discovery_tab.list_widget.count() == 1
        assert window.discovery_tab.list_widget.item(0).text() == "historic-only"
        assert "historic-only" not in runtime.snapshot().discoveries
        runtime.service.simulation.session.state.discoveries.add("current-only")
        window.advance()
        items = [window.discovery_tab.list_widget.item(i).text() for i in range(window.discovery_tab.list_widget.count())]
        assert "current-only" in items and items.count("historic-only") == 1
        assert "historic-only" not in runtime.snapshot().discoveries
    finally:
        runtime.stop()
        window.shutdown()


def test_write_notice_appears_and_clears_without_modal(tmp_path):
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    window = build_main_window(runtime)
    window.show()
    window.timer.stop()
    try:
        assert window.storage_notice.isHidden()
        with patch("miniatured_world.persistence.store.os.replace", side_effect=OSError("private-marker")):
            window.advance()
        app.processEvents()
        assert window.storage_notice.isVisible()
        assert "保存できていません" in window.storage_notice.text()
        assert "private-marker" not in window.storage_notice.text()
        assert app.activeModalWidget() is None
        runtime.service.store.retry_pending(force=True)
        window.refresh(runtime.snapshot())
        assert window.storage_notice.isHidden()
    finally:
        runtime.stop()
        window.shutdown()


def test_new_discovery_visible_when_old_file_is_protected(tmp_path):
    app = QApplication.instance() or QApplication([])
    (tmp_path / "discovery.json").write_bytes(b"{")
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    window = build_main_window(runtime)
    window.timer.stop()
    try:
        runtime.service.simulation.session.state.discoveries.add("new-only")
        window.advance()
        assert any(window.discovery_tab.list_widget.item(i).text() == "new-only" for i in range(window.discovery_tab.list_widget.count()))
        assert (tmp_path / "discovery.json").read_bytes() == b"{"
        assert "保存されません" in window.storage_notice.text()
    finally:
        runtime.stop()
        window.shutdown()
