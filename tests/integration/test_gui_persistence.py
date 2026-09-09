"""実際の起動経路で、一時実行と通常保存の境界を検査する。"""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

pytest.importorskip("PySide6")


def _run(tmp_path: Path, *arguments: str):
    log = tmp_path / "diagnostic.jsonl"
    result = subprocess.run(
        [
            sys.executable, "-m", "miniatured_world",
            "--activity-provider", "demo",
            "--duration-seconds", "0.1", "--tick-interval-ms", "20",
            "--stability-log", str(log), *arguments,
        ],
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
            "QT_QPA_PLATFORM": "offscreen",
            "MINIATURED_WORLD_DATA_DIR": str(tmp_path / "default-data"),
        },
        capture_output=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stderr
    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert entries[-1]["event"] == "completed"
    assert entries[-1]["frames"] == 5


@pytest.mark.parametrize("explicit_root", [False, True])
@pytest.mark.parametrize("existing_data", [False, True])
def test_ephemeral_gui_neither_loads_nor_saves_data(tmp_path, explicit_root, existing_data):
    roots = [tmp_path / "default-data", tmp_path / "explicit-data"]
    original = {}
    if existing_data:
        for root in roots:
            root.mkdir()
            for name in ("settings.json", "discovery.json"):
                # 読み込むと起動に失敗するため、読み取りの混入も検出できる。
                path = root / name
                path.write_bytes(b"{deliberately invalid test json")
                original[path] = (path.read_bytes(), path.stat().st_mtime_ns)
    arguments = ["--ephemeral"]
    if explicit_root:
        arguments += ["--data-root", str(roots[1])]
    _run(tmp_path, *arguments)
    if existing_data:
        assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for root in roots for path in root.rglob("*") if path.is_file()} == original
    else:
        assert all(not root.exists() for root in roots)


@pytest.mark.parametrize("explicit_root", [False, True])
def test_normal_gui_saves_only_to_selected_root(tmp_path, explicit_root):
    default_root, explicit = tmp_path / "default-data", tmp_path / "explicit-data"
    arguments = ["--data-root", str(explicit)] if explicit_root else []
    _run(tmp_path, *arguments)
    selected, unused = (explicit, default_root) if explicit_root else (default_root, explicit)
    assert json.loads((selected / "settings.json").read_text(encoding="utf-8"))["schema_version"] == 1
    assert json.loads((selected / "discovery.json").read_text(encoding="utf-8"))["schema_version"] == 1
    assert not unused.exists()


def test_ephemeral_cli_preserves_the_same_no_storage_contract(tmp_path):
    _run(tmp_path, "--no-ui", "--ephemeral", "--data-root", str(tmp_path / "explicit-data"))
    assert not (tmp_path / "default-data").exists()
    assert not (tmp_path / "explicit-data").exists()
