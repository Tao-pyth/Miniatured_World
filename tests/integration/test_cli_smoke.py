import os
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
