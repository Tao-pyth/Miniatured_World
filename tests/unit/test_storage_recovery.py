import json
from dataclasses import asdict, replace

import pytest

from miniatured_world.app.runtime import AppRuntime
from miniatured_world.persistence import DiscoveryRecord, JsonStore, Settings


@pytest.mark.parametrize("raw", [
    b'{', b'', b'\xff', b'null', b'[]', b'"private-file-content"',
    b'{"schema_version":999}', b'{"schema_version":true}',
    b'{"future_field":"private-file-content"}',
    b'{"activity":null}', b'{"activity":{"enabled":"false"}}',
    b'{"activity":{"enabled":0}}', b'{"display":{"opacity":NaN}}',
    b'{"display":{"opacity":1e300}}', b'{"display":{"fps_limit":-1}}',
    b'{"activity":{"enabled":false,"enabled":true}}',
    b'{"activity":{"future_field":true}}', b'{"activity_notice":{}}',
    b'{"privacy":{"store_raw_input":true}}',
])
def test_invalid_settings_are_preserved_while_healthy_discovery_keeps_saving(tmp_path, raw):
    path = tmp_path / "settings.json"
    path.write_bytes(raw)
    JsonStore(tmp_path).save_discovery(DiscoveryRecord(discoveries=["existing-discovery"]))
    for _ in range(2):
        runtime = AppRuntime.start(seed=42, data_root=tmp_path)
        assert not runtime.state.activity_collection_enabled
        assert runtime.service.store.issues[0].name == "settings.json"
        assert "existing-discovery" in runtime.service.discovery_manager.discoveries
        runtime.service.simulation.session.state.discoveries.add("new-discovery")
        runtime.tick()
        runtime.update_setting("display", "opacity", 0.7)
        runtime.set_activity_collection(True)
        runtime.tick()
        runtime.stop()
        assert path.read_bytes() == raw
        assert {"existing-discovery", "new-discovery"} <= set(JsonStore(tmp_path).load_discovery().discoveries)
        assert "private-file-content" not in repr(runtime.service.store.issues)
        assert "private-file-content" not in runtime.service.store.issues[0].message
    assert sorted(p.name for p in tmp_path.iterdir()) == ["discovery.json", "settings.json"]


@pytest.mark.parametrize("raw", [b'{', b'\xff', b'[]', b'{"discoveries":"secret"}',
                                 b'{"discoveries":[{}]}', b'{"schema_version":2}', b'{"future":true}'])
def test_invalid_discovery_preserved_and_healthy_settings_keep_saving(tmp_path, raw):
    path = tmp_path / "discovery.json"
    path.write_bytes(raw)
    settings = replace(Settings(), activity=replace(Settings().activity, enabled=False), activity_notice="shown")
    JsonStore(tmp_path).save_settings(settings)
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    assert runtime.service.settings == settings
    runtime.update_setting("display", "opacity", 0.6)
    runtime.service.simulation.session.state.discoveries.add("in-memory-only")
    runtime.tick()
    assert "in-memory-only" in runtime.service.discovery_manager.discoveries
    assert JsonStore(tmp_path).load_settings().display.opacity == 0.6
    assert path.read_bytes() == raw
    assert runtime.service.store.issues[0].name == "discovery.json"


def test_both_invalid_and_direct_save_cannot_bypass_protection(tmp_path):
    for name in ("settings.json", "discovery.json"):
        (tmp_path / name).write_bytes(b'{')
    store = JsonStore(tmp_path)
    assert store.save_settings(Settings()) is None
    assert store.save_discovery(DiscoveryRecord()) is None
    assert len(store.issues) == 2
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    assert runtime.tick().world_time > 0
    assert all((tmp_path / name).read_bytes() == b'{' for name in ("settings.json", "discovery.json"))


def test_repaired_file_requires_a_new_store_before_saving(tmp_path):
    path = tmp_path / "settings.json"
    path.write_bytes(b'{')
    store = JsonStore(tmp_path)
    store.load_settings()
    repaired = json.dumps(asdict(Settings())).encode()
    path.write_bytes(repaired)  # 利用者による修復・復元を模擬する。
    assert store.save_settings(Settings()) is None
    store.load_settings()
    assert store.issues and path.read_bytes() == repaired
    restarted = JsonStore(tmp_path)
    assert restarted.load_settings() == Settings()
    assert restarted.save_settings(Settings()) == path
    assert not restarted.issues


def test_unreadable_file_preserves_bytes_without_exposing_exception(tmp_path, monkeypatch):
    from pathlib import Path
    path = tmp_path / "settings.json"
    path.write_bytes(b'{}')
    original = Path.read_text

    def denied(self, *args, **kwargs):
        if self == path:
            raise PermissionError("private-file-content")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", denied)
    store = JsonStore(tmp_path)
    assert not store.load_settings().activity.enabled
    assert store.save_settings(Settings()) is None
    assert path.read_bytes() == b'{}'
    assert "private-file-content" not in store.issues[0].message


def test_valid_off_and_save_preferences_remain_unchanged(tmp_path):
    settings = replace(Settings(), activity=replace(Settings().activity, enabled=False),
                       data=replace(Settings().data, save_discovery=False, save_settings=False))
    store = JsonStore(tmp_path)
    store.save_settings(settings)
    store.save_discovery(DiscoveryRecord(discoveries=["existing"]))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    runtime.tick()
    assert runtime.service.settings == settings
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert not runtime.service.store.issues
