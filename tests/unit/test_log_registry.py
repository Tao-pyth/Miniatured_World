import json
from pathlib import Path
from unittest.mock import patch

import pytest

from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.stability import StabilityLogWriter
from miniatured_world.persistence.log_registry import LogRegistry, identify_log
from miniatured_world.persistence import JsonStore


def writer_for(runtime, path, *, tracked=True):
    writer = StabilityLogWriter(log_path=path, duration_seconds=10, tick_interval_ms=1000, realtime=False, registry=runtime.service.log_registry if tracked else None)
    writer.start(runtime.snapshot())
    return writer


def test_log_paths_survive_restart_without_storing_log_contents(tmp_path):
    root = tmp_path / "data"
    runtime = AppRuntime.start(42, data_root=root)
    assert not root.exists()
    logs = [tmp_path / "outside" / "first.jsonl", root / "second.jsonl"]
    for path in logs:
        writer_for(runtime, path).close()
    record = json.loads((root / "log-index.json").read_text())
    assert record["schema_version"] == 1 and len(record["logs"]) == 2
    assert all(set(entry) == {"path", "sha256"} for entry in record["logs"])
    restored = LogRegistry(JsonStore(root))
    assert {entry.path for entry in restored.entries} == {str(path.resolve()) for path in logs}
    result = restored.delete(restored.entries)
    assert all(result.values()) and all(not path.exists() for path in logs)
    assert not (root / "log-index.json").exists()


def test_delete_closes_current_writer_and_never_recreates_log_or_index(tmp_path):
    runtime = AppRuntime.start(42, data_root=tmp_path / "data")
    path = tmp_path / "current.jsonl"
    writer = writer_for(runtime, path)
    registry = runtime.service.log_registry
    before = runtime.snapshot().world_time
    assert all(registry.delete(registry.entries).values())
    assert writer.closed
    for index in range(3):
        writer.tick(index, runtime.tick(), runtime.service.summary_text())
    runtime.stop()
    assert runtime.snapshot().world_time > before
    assert not path.exists() and not (runtime.service.store.root / "log-index.json").exists()
    assert (runtime.service.store.root / "settings.json").exists()


def test_legacy_log_can_be_selected_and_new_or_unrelated_files_are_rejected(tmp_path):
    runtime = AppRuntime.start(42, data_root=tmp_path / "data")
    path = tmp_path / "legacy.jsonl"
    writer_for(runtime, path, tracked=False).close()
    header = json.loads(path.read_text(encoding="utf-8"))
    header.pop("application")
    header.pop("log_schema_version")
    path.write_text(json.dumps(header) + "\n", encoding="utf-8")
    entry = identify_log(path)
    assert not runtime.service.log_registry.entries
    assert all(runtime.service.log_registry.delete([entry]).values())
    assert not path.exists()
    for content in ("user text\n", '{"event":"start"}\n', json.dumps(dict(header, application="another-app")) + "\n"):
        path.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError):
            identify_log(path)
        assert path.read_text(encoding="utf-8") == content


def test_replaced_log_and_unrelated_siblings_are_kept(tmp_path):
    runtime = AppRuntime.start(42, data_root=tmp_path / "data")
    path = tmp_path / "modified.jsonl"
    writer = writer_for(runtime, path)
    entries = runtime.service.log_registry.entries
    writer.close()
    path.write_bytes(b"unrelated replacement")
    unknown = tmp_path / "unknown.txt"
    unknown.write_bytes(b"keep")
    result = runtime.service.log_registry.delete(entries)
    assert not result[str(path.resolve())]
    assert path.read_bytes() == b"unrelated replacement" and unknown.read_bytes() == b"keep"
    assert runtime.service.log_registry.entries == entries


@pytest.mark.parametrize("raw", [b"{broken private fixture", b'{"schema_version":99}', b'{"logs":[{"path":"relative","sha256":"bad"}]}'])
def test_corrupt_catalog_is_protected_while_other_storage_continues(tmp_path, raw, caplog):
    root = tmp_path / "data"
    root.mkdir()
    index = root / "log-index.json"
    index.write_bytes(raw)
    runtime = AppRuntime.start(42, data_root=root)
    path = tmp_path / "current.jsonl"
    writer = writer_for(runtime, path)
    runtime.tick()
    registry = runtime.service.log_registry
    assert registry.protected and registry.entries
    result = registry.delete(registry.entries)
    assert result[str(path.resolve())] and not result["log-index.json"]
    assert writer.closed and index.read_bytes() == raw
    assert (root / "settings.json").exists() and (root / "discovery.json").exists()
    assert "private fixture" not in caplog.text


def test_catalog_write_failure_then_delete_cancels_stale_metadata(tmp_path):
    runtime = AppRuntime.start(42, data_root=tmp_path / "data")
    original = __import__("os").replace
    def fail(source, target):
        if Path(target).name == "log-index.json":
            raise PermissionError("private value")
        return original(source, target)
    path = tmp_path / "log.jsonl"
    with patch("miniatured_world.persistence.store.os.replace", fail):
        writer = writer_for(runtime, path)
        runtime.tick()
    assert "log-index.json" in runtime.service.store._pending
    assert all(runtime.service.log_registry.delete(runtime.service.log_registry.entries).values())
    runtime.service.retry_pending_saves(force=True)
    writer.tick(2, runtime.tick(), runtime.service.summary_text())
    assert not path.exists() and not (tmp_path / "data/log-index.json").exists()
    assert not list((tmp_path / "data").glob("*.tmp"))


def test_missing_registered_file_is_removed_without_touching_another_log(tmp_path):
    runtime = AppRuntime.start(42, data_root=tmp_path / "data")
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    writer_for(runtime, a).close()
    writer_for(runtime, b).close()
    entry = identify_log(a)
    a.unlink()
    assert all(runtime.service.log_registry.delete([entry]).values())
    assert b.exists() and len(runtime.service.log_registry.entries) == 1


@pytest.mark.skipif(__import__("sys").platform != "win32", reason="Windows delete sharing")
def test_real_windows_locked_log_can_be_deleted_after_release(tmp_path):
    import ctypes
    runtime = AppRuntime.start(42, data_root=tmp_path / "data")
    path = tmp_path / "locked.jsonl"
    writer = writer_for(runtime, path)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateFileW(str(path), 0x80000000, 3, None, 3, 0, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        result = runtime.service.log_registry.delete(runtime.service.log_registry.entries)
        assert not result[str(path.resolve())] and writer.closed
        before = path.read_bytes()
        writer.tick(1, runtime.tick(), runtime.service.summary_text())
        assert path.read_bytes() == before
    finally:
        kernel.CloseHandle(handle)
    restored = LogRegistry(JsonStore(tmp_path / "data"))
    assert all(restored.delete(restored.entries).values())
    assert not path.exists()


def test_ephemeral_explicit_log_does_not_read_or_create_registry(tmp_path):
    runtime = AppRuntime.start(42)
    with patch.object(JsonStore, "load_log_index", side_effect=AssertionError("no registry read")):
        writer = writer_for(runtime, tmp_path / "explicit.jsonl")
        writer.close()
    assert (tmp_path / "explicit.jsonl").exists()
    assert not runtime.service.log_registry.entries
    assert runtime.service.log_registry.delete([identify_log(tmp_path / "explicit.jsonl")]) == {}


def test_symlink_log_is_not_a_deletion_candidate(tmp_path):
    runtime = AppRuntime.start(42)
    original, link = tmp_path / "original.jsonl", tmp_path / "link.jsonl"
    writer_for(runtime, original, tracked=False).close()
    try:
        link.symlink_to(original)
    except OSError:
        pytest.skip("Symlink creation unavailable")
    with pytest.raises(ValueError):
        identify_log(link)
    assert original.exists()


@pytest.mark.parametrize("content", [b"[" * 2000 + b"0" + b"]" * 2000 + b"\n", b"x" * 9000 + b"\n", b'{}', b'\xff\xfe\x00\n'])
def test_malformed_or_unbounded_header_is_rejected_without_content_echo(tmp_path, content):
    path = tmp_path / "invalid.jsonl"
    path.write_bytes(content)
    with pytest.raises(ValueError):
        identify_log(path)
    assert path.read_bytes() == content


@pytest.mark.skipif(__import__("sys").platform != "win32", reason="Windows junction")
def test_changed_parent_junction_never_deletes_the_replacement(tmp_path):
    import subprocess
    runtime = AppRuntime.start(42, data_root=tmp_path / "data")
    folder = tmp_path / "original"
    path = folder / "log.jsonl"
    writer_for(runtime, path).close()
    entry = identify_log(path)
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    same_content = path.read_bytes()
    (replacement / "log.jsonl").write_bytes(same_content)
    saved = tmp_path / "saved-original"
    assert folder.resolve().parent == tmp_path.resolve() and saved.resolve().parent == tmp_path.resolve()
    folder.rename(saved)
    run = subprocess.run(["cmd", "/c", "mklink", "/J", str(folder), str(replacement)], capture_output=True)
    assert run.returncode == 0
    try:
        assert path.resolve() != Path(entry.path)
        result = runtime.service.log_registry.delete([entry])
        assert not result[entry.path]
        assert (replacement / "log.jsonl").read_bytes() == same_content
        assert (saved / "log.jsonl").read_bytes() == same_content
    finally:
        assert folder.is_junction() and folder.resolve().is_relative_to(tmp_path.resolve())
        folder.rmdir()
