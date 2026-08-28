import os
import json
import subprocess
import sys


def test_cli_demo_provider_smoke_outputs_japanese_summary() -> None:
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "miniatured_world",
            "--no-ui",
            "--ephemeral",
            "--frames",
            "5",
            "--activity-provider",
            "demo",
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
        env=env,
    )

    assert "Miniatured World シード=20260825" in result.stdout
    assert "傾向=森" in result.stdout
    assert "発見=" in result.stdout


def test_cli_accepts_windows_global_provider() -> None:
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "miniatured_world",
            "--no-ui",
            "--ephemeral",
            "--frames",
            "1",
            "--activity-provider",
            "windows-global",
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
        env=env,
    )

    assert "Miniatured World シード=20260825" in result.stdout


def test_cli_writes_stability_log(tmp_path) -> None:
    env = {**os.environ, "PYTHONPATH": "src"}
    log_path = tmp_path / "stability.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "miniatured_world",
            "--no-ui",
            "--ephemeral",
            "--frames",
            "2",
            "--activity-provider",
            "demo",
            "--stability-log",
            str(log_path),
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
        env=env,
    )

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert "安定性ログ=" in result.stdout
    assert entries[0]["event"] == "start"
    assert entries[-1]["event"] == "completed"
    assert entries[-1]["snapshot"]["provider"]["name"] == "demo"
