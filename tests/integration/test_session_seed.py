import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from miniatured_world import __main__ as entry
from miniatured_world.app import qt_app


@pytest.mark.parametrize("mode", ["gui", "cli", "fallback"])
def test_omitted_seed_is_generated_once_per_launch(monkeypatch, capsys, mode):
    generated = iter((123456, 987654))
    calls = []
    gui_seeds = []

    def randbits(bits):
        calls.append(bits)
        return next(generated)

    def gui(**kwargs):
        gui_seeds.append(kwargs["seed"])
        if mode == "fallback":
            raise ImportError("test-only unavailable Qt")
        return 0

    monkeypatch.setattr(entry.secrets, "randbits", randbits)
    monkeypatch.setattr(qt_app, "run_qt_app", gui)
    for expected in (123456, 987654):
        args = ["--ephemeral", "--activity-provider", "none", "--frames", "1"]
        if mode == "cli":
            args.append("--no-ui")
        assert entry.main(args) == 0
        captured = capsys.readouterr()
        if mode != "gui":
            assert f"シード={expected} " in captured.out
    assert calls == [64, 64]
    assert gui_seeds == ([] if mode == "cli" else [123456, 987654])


@pytest.mark.parametrize("mode", ["gui", "cli"])
@pytest.mark.parametrize("seed", [20260825, 0, -42])
def test_explicit_seed_is_preserved_without_entropy(monkeypatch, capsys, mode, seed):
    monkeypatch.setattr(entry.secrets, "randbits", lambda bits: pytest.fail("明示seedで再生成"))
    seen = []
    monkeypatch.setattr(qt_app, "run_qt_app", lambda **kwargs: seen.append(kwargs["seed"]) or 0)
    args = ["--ephemeral", "--activity-provider", "none", "--seed", str(seed)]
    if mode == "cli":
        args.append("--no-ui")
    assert entry.main(args) == 0
    if mode == "gui":
        assert seen == [seed]
    else:
        assert f"シード={seed} " in capsys.readouterr().out


@pytest.mark.parametrize("arguments,code", [(["--help"], 0), (["--seed", "invalid"], 2)])
def test_no_seed_generation_for_help_or_invalid_arguments(monkeypatch, arguments, code):
    monkeypatch.setattr(entry.secrets, "randbits", lambda bits: pytest.fail("起動しない引数で生成"))
    with pytest.raises(SystemExit) as raised:
        entry.main(arguments)
    assert raised.value.code == code


@pytest.mark.parametrize("gui", [False, True])
def test_process_generated_seed_can_reproduce_world_with_explicit_seed(tmp_path, gui):
    if gui:
        pytest.importorskip("PySide6")
    env = {
        **os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
        "QT_QPA_PLATFORM": "offscreen", "MINIATURED_WORLD_DATA_DIR": str(tmp_path / "unused-data"),
    }
    def run(name, seed=None):
        log = tmp_path / f"{name}.jsonl"
        args = [sys.executable, "-m", "miniatured_world", "--ephemeral", "--activity-provider", "demo",
                "--duration-seconds", "0.1", "--tick-interval-ms", "20", "--stability-log", str(log)]
        if not gui:
            args.append("--no-ui")
        if seed is not None:
            args += ["--seed", str(seed)]
        result = subprocess.run(args, env=env, capture_output=True, encoding="utf-8", timeout=25)
        assert result.returncode == 0, result.stderr
        entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        assert entries[-1]["event"] == "completed"
        return entries[-1]["snapshot"]

    generated = run("generated")
    assert type(generated["seed"]) is int
    assert 0 <= generated["seed"] < 2**64
    assert run("replayed", generated["seed"]) == generated
    assert not (tmp_path / "unused-data").exists()
