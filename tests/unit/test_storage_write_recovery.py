import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from miniatured_world.app.runtime import AppRuntime
from miniatured_world.persistence import JsonStore, Settings, DiscoveryRecord


@pytest.mark.parametrize("blocked", [("settings.json",), ("discovery.json",), ("settings.json", "discovery.json")])
def test_write_failure_isolated_latest_retry_and_bounded_temporary(tmp_path, blocked, caplog):
    initial = JsonStore(tmp_path)
    initial.save_settings(Settings())
    initial.save_discovery(DiscoveryRecord(discoveries=["old"]))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    store = runtime.service.store
    now = [1.0]
    store._clock = lambda: now[0]
    original_replace = __import__("os").replace
    calls = []

    def denied(source, target):
        if Path(target).name in blocked:
            calls.append(Path(target).name)
            raise PermissionError("private-value-and-path")
        return original_replace(source, target)

    with patch("miniatured_world.persistence.store.os.replace", denied):
        runtime.service.simulation.session.state.discoveries.add("new")
        assert runtime.tick().world_time > 0
        for name in blocked:
            assert (tmp_path / name).read_bytes() == before[name]
        if "discovery.json" not in blocked:
            assert "new" in json.loads((tmp_path / "discovery.json").read_text())["discoveries"]
        if "settings.json" not in blocked:
            assert not store.save_settings(replace(Settings(), activity_notice="shown")) is None
        for _ in range(100):
            runtime.tick()
        assert len(calls) == len(blocked)
        runtime.update_setting("display", "opacity", 0.45)
        for retry in range(1, 4):
            now[0] = 1.0 + retry * 5
            runtime.tick()
            assert len(list(tmp_path.glob("*.tmp"))) == len(blocked)
    assert "private-value-and-path" not in caplog.text
    assert all(issue.reason == "write_failed" for issue in store.issues)
    now[0] += 5
    runtime.tick()
    assert not store.issues
    assert not list(tmp_path.glob("*.tmp"))
    assert json.loads((tmp_path / "settings.json").read_text())["display"]["opacity"] == 0.45
    assert {"old", "new"} <= set(json.loads((tmp_path / "discovery.json").read_text())["discoveries"])


@pytest.mark.parametrize("stage", ["mkdir", "temporary", "write", "replace"])
def test_each_io_failure_preserves_original_then_recovers(tmp_path, stage):
    store = JsonStore(tmp_path)
    store.save_settings(Settings())
    before = (tmp_path / "settings.json").read_bytes()
    target = {
        "mkdir": "miniatured_world.persistence.store.Path.mkdir",
        "temporary": "miniatured_world.persistence.store.NamedTemporaryFile",
        "write": "miniatured_world.persistence.store.json.dump",
        "replace": "miniatured_world.persistence.store.os.replace",
    }[stage]
    with patch(target, side_effect=OSError("secret")):
        assert store.save_settings(replace(Settings(), activity_notice="shown")) is None
    assert (tmp_path / "settings.json").read_bytes() == before
    assert len(store.issues) == 1
    store.retry_pending(force=True)
    assert not store.issues
    assert json.loads((tmp_path / "settings.json").read_text())["activity_notice"] == "shown"


@pytest.mark.parametrize("pause", ["manual", "system"])
def test_retry_while_paused_does_not_advance_world(tmp_path, pause):
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    store = runtime.service.store
    now = [1.0]
    store._clock = lambda: now[0]
    with patch("miniatured_world.persistence.store.os.replace", side_effect=PermissionError):
        runtime.tick()
    before = runtime.snapshot().world_time
    if pause == "manual":
        runtime.pause()
    else:
        runtime.set_system_suspended("lock", True)
    now[0] = 6.0
    assert runtime.tick().world_time == before
    assert not store.issues
    assert runtime.snapshot().paused


def test_stop_retries_once_without_cooldown(tmp_path):
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    with patch("miniatured_world.persistence.store.os.replace", side_effect=PermissionError) as write:
        runtime.tick()
        assert write.call_count == 2
        runtime.stop()
        assert write.call_count == 4
        runtime.stop()
        runtime.tick()
        assert write.call_count == 4


def test_disable_discovery_cancels_pending_and_settings_off_choice_retries(tmp_path):
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    runtime.service.store._clock = lambda: 1.0
    with patch("miniatured_world.persistence.store.os.replace", side_effect=PermissionError):
        runtime.tick()
        runtime.update_setting("data", "save_discovery", False)
        runtime.update_setting("data", "save_settings", False)
    runtime.service.store._clock = lambda: 6.0
    runtime.tick()
    runtime.stop()
    assert not (tmp_path / "discovery.json").exists()
    assert not list(tmp_path.glob(".discovery.json.*.tmp"))
    saved = json.loads((tmp_path / "settings.json").read_text())
    assert not saved["data"]["save_discovery"]
    assert not saved["data"]["save_settings"]
    assert not runtime.service.store.issues


def test_retry_never_overwrites_read_protected_file(tmp_path):
    (tmp_path / "settings.json").write_bytes(b"{")
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    with patch("miniatured_world.persistence.store.os.replace", side_effect=PermissionError):
        runtime.tick()
    runtime.stop()
    assert (tmp_path / "settings.json").read_bytes() == b"{"
    assert (tmp_path / "discovery.json").is_file()
    assert [(i.name, i.reason) for i in runtime.service.store.issues] == [("settings.json", "unreadable")]


def test_temporary_close_failure_is_recoverable(tmp_path):
    from tempfile import NamedTemporaryFile
    store = JsonStore(tmp_path)
    store.save_settings(Settings())
    before = (tmp_path / "settings.json").read_bytes()

    class CloseFailure:
        def __init__(self, *args, **kwargs):
            self.handle = NamedTemporaryFile(*args, **kwargs)
            self.name = self.handle.name
        def __enter__(self):
            return self.handle
        def __exit__(self, *args):
            self.handle.close()
            raise OSError("private-close-error")

    with patch("miniatured_world.persistence.store.NamedTemporaryFile", CloseFailure):
        assert store.save_settings(replace(Settings(), activity_notice="shown")) is None
    assert (tmp_path / "settings.json").read_bytes() == before
    store.retry_pending(force=True)
    assert not store.issues
    assert not list(tmp_path.glob("*.tmp"))


def test_cli_exit_retries_pending_once(tmp_path):
    from miniatured_world.__main__ import main
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    with patch("miniatured_world.__main__.AppRuntime.start", return_value=runtime):
        with patch("miniatured_world.persistence.store.os.replace", side_effect=PermissionError) as write:
            assert main(["--no-ui", "--activity-provider", "none", "--frames", "2"]) == 0
            assert write.call_count == 4
    assert not runtime.state.running
