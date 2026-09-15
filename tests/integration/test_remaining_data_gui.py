from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.stability import StabilityLogWriter


def make_window(tmp_path, *, logged=True, ephemeral=False):
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(42, data_root=None if ephemeral else tmp_path / "data")
    runtime.tick()
    window = build_main_window(runtime, stability_log=tmp_path / "active.jsonl" if logged else None)
    window.timer.stop()
    return app, runtime, window


def choose(window, target, actions=("削除する",)):
    app = QApplication.instance()
    remaining = list(actions)
    timer = QTimer(window)
    observed = []
    def answer():
        dialog = app.activeModalWidget()
        if not isinstance(dialog, QMessageBox) or not remaining:
            return
        assert dialog.defaultButton().text() == "キャンセル"
        observed.append(dialog.text())
        name = remaining.pop(0)
        next(b for b in dialog.buttons() if b.text() == name).click()
    timer.timeout.connect(answer)
    timer.start(10)
    try:
        window.findChild(QPushButton, f"delete_{target}").click()
        assert not remaining
    finally:
        timer.stop()
    return observed


@pytest.mark.parametrize("target", ["logs", "cache", "all"])
def test_cancel_preserves_files_catalog_and_runtime(tmp_path, target):
    app, runtime, window = make_window(tmp_path)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    state = deepcopy(runtime.service.simulation.session.state)
    try:
        choose(window, target, ("キャンセル",))
        assert before == {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
        assert runtime.service.simulation.session.state == state
        assert not window._stability_logger.closed
    finally:
        runtime.stop()
        window.shutdown()


def test_all_deletes_known_data_stops_logging_and_preserves_unknown_files(tmp_path):
    app, runtime, window = make_window(tmp_path)
    unknown = tmp_path / "data/unknown.txt"
    unknown.write_bytes(b"keep")
    runtime.pause()
    old_time = runtime.snapshot().world_time
    try:
        choose(window, "all")
        assert not (tmp_path / "active.jsonl").exists()
        assert sorted(p.name for p in (tmp_path / "data").iterdir()) == ["unknown.txt"]
        assert runtime.state.paused and runtime.snapshot().world_time == old_time
        assert not runtime.state.activity_collection_enabled
        assert not runtime.service.settings.data.save_settings and not runtime.service.settings.data.save_discovery
        runtime.resume()
        window.advance()
        runtime.stop()
        assert runtime.snapshot().world_time > old_time
        assert not (tmp_path / "active.jsonl").exists()
        assert unknown.read_bytes() == b"keep"
    finally:
        runtime.stop()
        window.shutdown()


def test_unregistered_legacy_log_can_be_added_to_all_with_confirmation(tmp_path):
    app, runtime, window = make_window(tmp_path)
    old = tmp_path / "older.jsonl"
    writer = StabilityLogWriter(log_path=old, duration_seconds=1, tick_interval_ms=1000, realtime=False)
    writer.start(runtime.snapshot())
    writer.close()
    header = json.loads(old.read_text(encoding="utf-8"))
    header.pop("application")
    header.pop("log_schema_version")
    old.write_text(json.dumps(header) + "\n", encoding="utf-8")
    try:
        with patch.object(QFileDialog, "getOpenFileNames", return_value=([str(old)], "")):
            observed = choose(window, "all", ("過去ログを追加", "削除する"))
        assert len(observed) == 2 and str(old) in observed[-1]
        assert not old.exists() and not (tmp_path / "active.jsonl").exists()
    finally:
        runtime.stop()
        window.shutdown()


def test_selected_log_cancel_does_not_add_it_to_catalog(tmp_path):
    app, runtime, window = make_window(tmp_path)
    old = tmp_path / "manual.jsonl"
    writer = StabilityLogWriter(log_path=old, duration_seconds=1, tick_interval_ms=1000, realtime=False)
    writer.start(runtime.snapshot())
    writer.close()
    before = (tmp_path / "data/log-index.json").read_bytes()
    try:
        with patch.object(QFileDialog, "getOpenFileNames", return_value=([str(old)], "")):
            choose(window, "selected_logs", ("キャンセル",))
        assert old.exists() and (tmp_path / "data/log-index.json").read_bytes() == before
    finally:
        runtime.stop()
        window.shutdown()


def asset_hashes(preview):
    pixmaps = {"background": preview._background, **preview._character_sprites, **preview._props, **preview._hand_assets}
    for name, frames in preview._cauldron_sprites.items():
        pixmaps.update({f"cauldron-{name}-{i}": p for i, p in enumerate(frames)})
    return {key: hashlib.sha256(bytes(value.toImage().constBits())).hexdigest() for key, value in pixmaps.items()}


def test_cache_reload_preserves_assets_world_and_animation(tmp_path):
    app, runtime, window = make_window(tmp_path, logged=False)
    preview = window.world_tab.preview
    state = deepcopy(runtime.service.simulation.session.state)
    animation = deepcopy(vars(preview.animation))
    assets = asset_hashes(preview)
    try:
        choose(window, "cache")
        assert "キャッシュを削除しました" in window.data_result.text()
        assert asset_hashes(preview) == assets
        assert runtime.service.simulation.session.state == state and vars(preview.animation) == animation
    finally:
        runtime.stop()
        window.shutdown()


def test_cache_reload_failure_keeps_existing_assets(tmp_path):
    app, runtime, window = make_window(tmp_path, logged=False)
    preview = window.world_tab.preview
    before = asset_hashes(preview)
    try:
        with patch.object(Path, "read_bytes", side_effect=OSError("private path")):
            choose(window, "cache")
        assert "キャッシュを削除できませんでした" in window.data_result.text()
        assert "private path" not in window.data_result.text()
        assert asset_hashes(preview) == before
    finally:
        runtime.stop()
        window.shutdown()


def test_all_with_unreadable_catalog_reports_partial_completion(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    original = b"{unreadable private index"
    (root / "log-index.json").write_bytes(original)
    app, runtime, window = make_window(tmp_path)
    try:
        choose(window, "all")
        assert "ログ管理一覧を削除できませんでした" in window.data_result.text()
        assert (root / "log-index.json").read_bytes() == original
        assert not (root / "settings.json").exists() and not (root / "discovery.json").exists()
        assert not (tmp_path / "active.jsonl").exists()
        assert "private index" not in window.storage_notice.text()
    finally:
        runtime.stop()
        window.shutdown()


def test_unrecognized_selected_file_is_kept_and_reported(tmp_path):
    app, runtime, window = make_window(tmp_path)
    other = tmp_path / "other.jsonl"
    other.write_bytes(b"not an application log")
    try:
        with patch.object(QFileDialog, "getOpenFileNames", return_value=([str(other)], "")):
            choose(window, "selected_logs")
        assert "削除できませんでした" in window.data_result.text()
        assert other.read_bytes() == b"not an application log"
        assert (tmp_path / "active.jsonl").exists() and not window._stability_logger.closed
    finally:
        runtime.stop()
        window.shutdown()
