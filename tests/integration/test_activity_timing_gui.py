import json
from pathlib import Path
import os
import subprocess
import sys
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QSpinBox
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.stability import run_stability_check
from miniatured_world.persistence import JsonStore


def test_gui_interval_change_preserves_duration_not_frame_count(tmp_path):
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(42)
    log = tmp_path / "run.jsonl"
    window = build_main_window(runtime, duration_seconds=2, stability_log=log)
    window.timer.stop()
    try:
        window.advance()  # 1000ms
        window.findChild(QSpinBox, "activity_frame_window_ms").setValue(200)
        window.refresh(runtime.snapshot())
        assert window.timer.interval() == 200
        for _ in range(4): window.advance()
        assert not window._stability_completed
        window.advance()
        assert window._stability_completed
        rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        assert rows[-1]["frames"] == 6
        assert sum(row["tick_interval_ms"] for row in rows if row["event"] == "tick") == 2000
        assert runtime.service.now_ms == 2000
    finally:
        runtime.stop(); window.shutdown()


def test_stability_log_records_effective_interval_and_exact_duration(tmp_path):
    runtime = AppRuntime.start(42)
    runtime.update_setting("activity", "frame_window_ms", 200)
    log = tmp_path / "run.jsonl"
    run_stability_check(runtime, log_path=log, duration_seconds=1.1, tick_interval_ms=1000)
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["tick_interval_ms"] == 200
    assert sum(row["tick_interval_ms"] for row in rows if row["event"] == "tick") == 1100
    assert rows[-1]["frames"] == 6 and runtime.service.now_ms == 1100


def test_cli_uses_saved_interval(tmp_path):
    runtime = AppRuntime.start(42, data_root=tmp_path / "data")
    runtime.update_setting("activity", "frame_window_ms", 200)
    log = tmp_path / "cli.jsonl"
    result = subprocess.run([sys.executable, "-m", "miniatured_world", "--no-ui", "--activity-provider", "none", "--data-root", str(tmp_path / "data"), "--duration-seconds", "2", "--stability-log", str(log)], capture_output=True, env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src")))
    assert result.returncode == 0
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["tick_interval_ms"] == 200 and rows[-1]["frames"] == 10
    assert rows[-1]["snapshot"]["world_time"] == pytest.approx(1.606)
