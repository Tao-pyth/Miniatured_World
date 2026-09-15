import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from miniatured_world.app.startup import (
    OWNER_KEY, RUN_KEY, StartupManager, StartupUnavailable, startup_command,
)


class Registry:
    def __init__(self):
        self.values = {}
        self.mutations = 0
        self.fail_at = None

    def read(self, key, name):
        return self.values.get((key, name))

    def _mutate(self):
        self.mutations += 1
        if self.mutations == self.fail_at:
            raise PermissionError("fixture")

    def write(self, key, name, value):
        self._mutate()
        self.values[key, name] = value

    def delete(self, key, name):
        self._mutate()
        self.values.pop((key, name), None)


@pytest.fixture
def setup(tmp_path):
    registry = Registry()
    command = '"C:\\Test App\\ラボ.exe" --data-root "C:\\Test Data"'
    manager = StartupManager(tmp_path, registry=registry, command_builder=lambda root: command)
    return registry, manager, command


def test_inspection_is_read_only_and_enable_disable_are_scoped(setup):
    registry, manager, command = setup
    registry.values[RUN_KEY, "AnotherApp"] = "keep"
    for _ in range(2):
        assert manager.inspect().registered is False
    assert registry.mutations == 0
    assert manager.set_enabled(True).succeeded
    assert manager.inspect().registered is True
    assert registry.values[RUN_KEY, manager.name] == command
    assert manager.set_enabled(False).succeeded
    assert registry.values == {(RUN_KEY, "AnotherApp"): "keep"}


@pytest.mark.parametrize("fail_at,registered", [(1, False), (2, False), (3, True)])
def test_partial_registration_failure_retains_recoverable_ownership(setup, fail_at, registered):
    registry, manager, command = setup
    registry.fail_at = fail_at
    result = manager.set_enabled(True)
    assert not result.succeeded and result.registered is registered
    registry.fail_at = None
    assert manager.set_enabled(True).succeeded
    assert manager.set_enabled(False).succeeded
    assert not registry.values


@pytest.mark.parametrize("offset,registered", [(1, True), (2, False)])
def test_partial_disable_can_be_retried(setup, offset, registered):
    registry, manager, command = setup
    manager.set_enabled(True)
    registry.fail_at = registry.mutations + offset
    result = manager.set_enabled(False)
    assert not result.succeeded and result.registered is registered
    registry.fail_at = None
    assert manager.set_enabled(False).succeeded
    assert not registry.values


def test_failed_upgrade_keeps_old_command_owned(setup):
    registry, manager, old = setup
    manager.set_enabled(True)
    manager.command_builder = lambda root: 'C:\\New\\Lab.exe --data-root C:\\Test'
    registry.fail_at = registry.mutations + 2
    result = manager.set_enabled(True)
    assert not result.succeeded and result.registered is True
    assert registry.values[RUN_KEY, manager.name] == old
    registry.fail_at = None
    assert manager.set_enabled(False).succeeded
    assert not registry.values


@pytest.mark.parametrize("bad", ["{broken", "{}", "[]", '{"schema_version":99}', '{"schema_version":1,"schema_version":1}', "x" * 8193])
def test_unknown_owner_record_is_protected(setup, bad):
    registry, manager, command = setup
    registry.values[OWNER_KEY, manager.name] = bad
    registry.values[RUN_KEY, manager.name] = command
    before = dict(registry.values)
    assert manager.inspect().registered is None
    assert not manager.set_enabled(False).succeeded
    assert not manager.set_enabled(True).succeeded
    assert registry.values == before and registry.mutations == 0


def test_foreign_command_and_different_profile_are_untouched(setup, tmp_path):
    registry, manager, command = setup
    other = StartupManager(tmp_path / "other", registry=registry, command_builder=lambda root: "other.exe")
    assert manager.name != other.name
    other.set_enabled(True)
    registry.values[RUN_KEY, manager.name] = "foreign.exe"
    before = dict(registry.values)
    assert not manager.set_enabled(False).succeeded
    assert not manager.set_enabled(True).succeeded
    assert registry.values == before


def test_external_run_change_during_enable_is_not_overwritten(setup, monkeypatch):
    registry, manager, command = setup
    original = registry.write

    def replace_after_owner(key, name, value):
        original(key, name, value)
        if key == OWNER_KEY:
            registry.values[RUN_KEY, name] = "external.exe"

    monkeypatch.setattr(registry, "write", replace_after_owner)
    assert not manager.set_enabled(True).succeeded
    assert registry.values[RUN_KEY, manager.name] == "external.exe"


def test_inaccessible_registration_reports_unknown_not_disabled(setup, monkeypatch):
    registry, manager, command = setup
    monkeypatch.setattr(registry, "read", Mock(side_effect=PermissionError()))
    state = manager.inspect()
    assert state.registered is None and not state.can_change
    assert not manager.set_enabled(True).succeeded
    assert registry.mutations == 0


def test_ephemeral_does_not_touch_registry_or_probe_executable():
    registry, builder = Mock(), Mock()
    manager = StartupManager(None, registry=registry, command_builder=builder)
    assert not manager.inspect().can_change
    assert not manager.set_enabled(True).succeeded
    assert not manager.set_enabled(False).succeeded
    assert not registry.mock_calls and not builder.mock_calls


@pytest.mark.parametrize("command", ["x" * 261, "😀" * 131, "bad\0command", "bad\ncommand", "\ud800", ""])
def test_invalid_command_never_changes_registry(setup, command):
    registry, manager, _ = setup
    manager.command_builder = lambda root: command
    assert not manager.set_enabled(True).succeeded
    assert registry.mutations == 0


def test_frozen_command_uses_persistent_executable_and_only_data_root(tmp_path, monkeypatch):
    executable = tmp_path / "Test App ラボ.exe"
    executable.touch()
    root = tmp_path / "Test Data 日本語"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "argv", [str(executable), "--ephemeral", "--seed", "42", "--duration-seconds", "1"])
    assert startup_command(root) == subprocess.list2cmdline([str(executable), "--data-root", str(root)])


def test_source_command_requires_same_installed_module(tmp_path, monkeypatch):
    import miniatured_world
    executable = tmp_path / "Python Env" / "python.exe"
    executable.parent.mkdir()
    executable.with_name("pythonw.exe").touch()
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    run = Mock(return_value=Mock(returncode=0, stdout=str(Path(miniatured_world.__file__)).encode("utf-8")))
    monkeypatch.setattr(subprocess, "run", run)
    root = tmp_path / "Data 日本語"
    assert startup_command(root) == subprocess.list2cmdline([str(executable.with_name("pythonw.exe")), "-I", "-m", "miniatured_world", "--data-root", str(root)])
    assert run.call_args.args[0][1] == "-I"
    assert "PySide6.QtWidgets" in run.call_args.args[0][-1]
    assert run.call_args.kwargs["cwd"] == executable.parent
    run.return_value.stdout = str(tmp_path / "different-install" / "__init__.py").encode()
    with pytest.raises(StartupUnavailable, match="インストール"):
        startup_command(root)


def test_failed_source_probe_does_not_register(setup, monkeypatch):
    registry, manager, _ = setup
    manager.command_builder = startup_command
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(subprocess, "run", Mock(return_value=Mock(returncode=1, stdout=b"")))
    status = manager.set_enabled(True)
    assert not status.succeeded and status.registered is False
    assert "インストール" in status.message
    assert registry.mutations == 0


def test_source_probe_timeout_is_reported_without_registry_changes(setup, monkeypatch):
    registry, manager, _ = setup
    manager.command_builder = startup_command
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=subprocess.TimeoutExpired("fixture", 5)))
    status = manager.set_enabled(True)
    assert not status.succeeded and status.registered is False
    assert registry.mutations == 0
