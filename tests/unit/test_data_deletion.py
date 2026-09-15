import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from miniatured_world.app.runtime import AppRuntime
from miniatured_world.persistence import DiscoveryRecord, JsonStore, Settings


def started(root):
    store = JsonStore(root)
    store.save_settings(replace(Settings(), activity_notice="shown"))
    store.save_discovery(DiscoveryRecord(discoveries=["past-only"]))
    runtime = AppRuntime.start(42, data_root=root)
    runtime.service.simulation.session.state.discoveries.add("current-old")
    runtime.tick()
    return runtime


@pytest.mark.parametrize("target,names", [("settings", {"settings.json"}), ("discovery", {"discovery.json"}), ("settings_and_discovery", {"settings.json", "discovery.json"})])
def test_deletion_survives_ticks_retry_and_exit_and_preserves_unknowns(tmp_path, target, names):
    runtime = started(tmp_path)
    sentinel = tmp_path / "keep.txt"
    sentinel.write_bytes(b"user-owned")
    other_tmp = tmp_path / ".settings.json.not-owned.tmp"
    other_tmp.write_bytes(b"unknown")
    old_time = runtime.snapshot().world_time
    for name in names:
        (tmp_path / f".{name}.abcd1234.tmp").write_bytes(b"orphaned pending fixture")
    result = runtime.delete_saved_data(target)
    assert result == dict.fromkeys(names, True)
    for _ in range(8):
        runtime.tick()
    runtime.service.retry_pending_saves(force=True)
    runtime.stop()
    assert runtime.snapshot().world_time > old_time
    assert all(not (tmp_path / name).exists() for name in names)
    assert not list(tmp_path.glob("*.abcd1234.tmp"))
    assert sentinel.read_bytes() == b"user-owned" and other_tmp.read_bytes() == b"unknown"
    if "discovery.json" not in names:
        assert "past-only" in json.loads((tmp_path / "discovery.json").read_text())["discoveries"]
    if "settings.json" not in names:
        assert not JsonStore(tmp_path).load_settings().data.save_discovery


def test_discovery_erasure_excludes_old_world_but_accepts_new_and_explicit_resume(tmp_path):
    runtime = started(tmp_path)
    assert runtime.delete_saved_data("discovery")["discovery.json"]
    runtime.tick()
    assert not ({"past-only", "current-old"} & runtime.service.discovery_manager.discoveries)
    runtime.service.simulation.session.state.discoveries.add("future-new")
    runtime.tick()
    assert "future-new" in runtime.service.discovery_manager.discoveries
    assert not (tmp_path / "discovery.json").exists()
    runtime.update_setting("data", "save_discovery", True)
    runtime.tick()
    persisted = JsonStore(tmp_path).load_discovery().discoveries
    assert "future-new" in persisted and not ({"past-only", "current-old"} & set(persisted))


def test_settings_reset_stops_capture_keeps_pause_and_waits_for_explicit_save(tmp_path):
    runtime = started(tmp_path)
    runtime.update_setting("activity", "frame_window_ms", 200)
    runtime.update_setting("data", "save_discovery", False)
    runtime.pause()
    runtime.set_system_suspended("lock", True)
    assert runtime.delete_saved_data("settings")["settings.json"]
    assert runtime.state.paused and runtime.state.system_pause_reasons == {"lock"}
    assert not runtime.state.activity_collection_enabled
    assert runtime.service.settings.activity_notice == "unseen"
    assert runtime.service.aggregator.frame_window_ms == 1000
    assert not runtime.service.settings.data.save_settings
    assert not runtime.service.settings.data.save_discovery
    runtime.update_setting("display", "opacity", 0.4)
    runtime.set_activity_collection(True)
    assert not (tmp_path / "settings.json").exists()
    runtime.update_setting("data", "save_settings", True)
    assert JsonStore(tmp_path).load_settings().display.opacity == 0.4


@pytest.mark.parametrize("name", ["settings.json", "discovery.json"])
@pytest.mark.parametrize("raw", [b"{private broken content", b'{"schema_version":999}'])
def test_protected_file_needs_successful_explicit_delete(tmp_path, name, raw):
    runtime = started(tmp_path)
    (tmp_path / name).write_bytes(raw)
    runtime = AppRuntime.start(42, data_root=tmp_path)
    assert any(issue.name == name for issue in runtime.service.store.issues)
    original_unlink = Path.unlink
    def denied(path, *args, **kwargs):
        if path == tmp_path / name:
            raise PermissionError("secret path")
        return original_unlink(path, *args, **kwargs)
    with patch.object(Path, "unlink", denied):
        assert not runtime.delete_saved_data(name.removesuffix(".json"))[name]
    assert (tmp_path / name).read_bytes() == raw
    assert any(issue.reason in ("unreadable", "unsupported") and issue.name == name for issue in runtime.service.store.issues)
    assert runtime.delete_saved_data(name.removesuffix(".json"))[name]
    assert not any(issue.name == name for issue in runtime.service.store.issues)


@pytest.mark.parametrize("name", ["settings.json", "discovery.json"])
@pytest.mark.parametrize("fail_delete", [False, True])
def test_pending_old_write_never_resurrects_after_deletion_request(tmp_path, name, fail_delete, caplog):
    runtime = started(tmp_path)
    original_replace = __import__("os").replace
    def deny_replace(source, target):
        if Path(target).name == name:
            raise PermissionError("private fixture")
        return original_replace(source, target)
    with patch("miniatured_world.persistence.store.os.replace", deny_replace):
        runtime.tick()
    assert name in runtime.service.store._pending
    original = (tmp_path / name).read_bytes()
    original_unlink = Path.unlink
    def unlink(path, *args, **kwargs):
        if fail_delete and path == tmp_path / name:
            raise PermissionError("private fixture")
        return original_unlink(path, *args, **kwargs)
    with patch.object(Path, "unlink", unlink):
        result = runtime.delete_saved_data(name.removesuffix(".json"))
    assert result[name] is not fail_delete
    for _ in range(6):
        runtime.tick()
    runtime.service.retry_pending_saves(force=True)
    runtime.stop()
    assert name not in runtime.service.store._pending
    if fail_delete:
        assert (tmp_path / name).read_bytes() == original
        runtime.service.store.resume_saving(name)
        assert name in runtime.service.store._erased
        assert runtime.service.store.delete_data(name)
    assert not (tmp_path / name).exists()
    assert "private fixture" not in caplog.text


def test_combined_partial_failure_reports_each_target(tmp_path):
    runtime = started(tmp_path)
    old_settings = (tmp_path / "settings.json").read_bytes()
    original = Path.unlink
    def denied(path, *args, **kwargs):
        if path.name == "settings.json":
            raise PermissionError()
        return original(path, *args, **kwargs)
    with patch.object(Path, "unlink", denied):
        result = runtime.delete_saved_data("settings_and_discovery")
    assert result == {"discovery.json": True, "settings.json": False}
    runtime.tick()
    assert not (tmp_path / "discovery.json").exists()
    assert (tmp_path / "settings.json").read_bytes() == old_settings


def test_outside_temporary_path_is_rejected_and_unknown_names_rejected(tmp_path):
    root = tmp_path / "data"
    runtime = started(root)
    outside = tmp_path / ".settings.json.abcd1234.tmp"
    outside.write_bytes(b"external")
    runtime.service.store._temporary["settings.json"] = outside
    assert not runtime.delete_saved_data("settings")["settings.json"]
    assert outside.read_bytes() == b"external" and (root / "settings.json").exists()
    for name in ("../keep.txt", "cache", "unknown.json"):
        with pytest.raises(ValueError):
            runtime.service.store.delete_data(name)


def test_ephemeral_does_not_access_any_store():
    runtime = AppRuntime.start(42)
    with patch.object(Path, "unlink", side_effect=AssertionError("no disk")):
        assert runtime.delete_saved_data("settings_and_discovery") == {}
    assert runtime.service.store is None


def test_reintroduced_invalid_file_is_protected_when_saving_resumes(tmp_path):
    runtime = started(tmp_path)
    runtime.delete_saved_data("settings")
    runtime.tick()
    path = tmp_path / "settings.json"
    path.write_bytes(b"invalid externally restored fixture")
    runtime.update_setting("data", "save_settings", True)
    runtime.tick()
    assert path.read_bytes() == b"invalid externally restored fixture"
    assert runtime.service.store.issues[0].reason == "unreadable"


@pytest.mark.parametrize("locked_name", ["settings.json", ".settings.json.abcd1234.tmp"])
@pytest.mark.skipif(__import__("sys").platform != "win32", reason="Windows file sharing contract")
def test_real_windows_delete_sharing_failure_then_retry(tmp_path, locked_name):
    import ctypes
    runtime = started(tmp_path)
    if locked_name.endswith(".tmp"):
        (tmp_path / locked_name).write_bytes(b"pending fixture")
    original = (tmp_path / "settings.json").read_bytes()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateFileW(str(tmp_path / locked_name), 0x80000000, 3, None, 3, 0, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        assert not runtime.delete_saved_data("settings")["settings.json"]
        runtime.tick()
        runtime.service.retry_pending_saves(force=True)
        assert (tmp_path / "settings.json").read_bytes() == original
        assert any(i.reason == "delete_failed" for i in runtime.service.store.issues)
        assert (tmp_path / "discovery.json").exists()
    finally:
        kernel.CloseHandle(handle)
    assert runtime.delete_saved_data("settings")["settings.json"]
    assert not (tmp_path / "settings.json").exists()
    assert not list(tmp_path.glob("*.tmp"))
