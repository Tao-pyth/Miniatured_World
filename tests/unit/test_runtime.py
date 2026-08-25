from dataclasses import fields

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.app.commands import RuntimeCommand
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.persistence import JsonStore, Settings, update_settings


def test_runtime_tick_with_demo_provider_returns_snapshot() -> None:
    runtime = AppRuntime.start(seed=42, provider=DemoActivityProvider())

    snapshot = runtime.tick()

    assert snapshot.seed == 42
    assert snapshot.running is True
    assert snapshot.world_visible is True
    assert snapshot.muted is False
    assert snapshot.tendency
    assert snapshot.creature_count >= 1
    assert snapshot.activity_level in {"quiet", "calm", "active", "intense"}
    assert snapshot.provider_status.name == "demo"
    assert snapshot.provider_status.display_name == "デモ"


def test_runtime_pause_prevents_world_time_advancement() -> None:
    runtime = AppRuntime.start(seed=42, provider=DemoActivityProvider())
    before = runtime.tick().world_time

    runtime.pause()
    paused = runtime.tick().world_time

    assert paused == before
    assert runtime.snapshot().paused is True


def test_runtime_activity_collection_can_be_disabled() -> None:
    runtime = AppRuntime.start(seed=42, provider=DemoActivityProvider())
    runtime.set_activity_collection(False)

    snapshot = runtime.tick()

    assert snapshot.activity_collection_enabled is False
    assert snapshot.activity_level == "quiet"


def test_snapshot_does_not_expose_raw_input_fields() -> None:
    snapshot_fields = {field.name for field in fields(AppRuntime.start(seed=42).snapshot())}

    forbidden_fields = {
        "raw",
        "raw_input",
        "key",
        "key_sequence",
        "mouse_x",
        "mouse_y",
        "coordinate",
        "window_title",
        "clipboard",
        "screen",
    }
    assert snapshot_fields.isdisjoint(forbidden_fields)


def test_runtime_commands_control_visibility_pause_activity_mute_and_exit() -> None:
    runtime = AppRuntime.start(seed=42, provider=DemoActivityProvider())

    assert runtime.handle(RuntimeCommand.HIDE_WORLD).world_visible is False
    assert runtime.handle(RuntimeCommand.SHOW_WORLD).world_visible is True
    assert runtime.handle(RuntimeCommand.PAUSE).paused is True
    assert runtime.handle(RuntimeCommand.RESUME).paused is False
    assert runtime.handle(RuntimeCommand.STOP_ACTIVITY).activity_collection_enabled is False
    assert runtime.handle(RuntimeCommand.START_ACTIVITY).activity_collection_enabled is True
    assert runtime.handle(RuntimeCommand.MUTE).muted is True
    assert runtime.handle(RuntimeCommand.UNMUTE).muted is False
    assert runtime.handle(RuntimeCommand.TOGGLE_MUTE).muted is True
    assert runtime.handle(RuntimeCommand.EXIT).running is False


def test_runtime_persists_setting_updates(tmp_path) -> None:
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)

    runtime.update_setting("display", "fps_limit", 60)
    runtime.update_setting("activity", "enabled", False)
    runtime.handle(RuntimeCommand.TOGGLE_MUTE)

    loaded = JsonStore(tmp_path).load_settings()
    assert loaded.display.fps_limit == 60
    assert loaded.activity.enabled is False
    assert loaded.sound.enabled is False
    assert runtime.snapshot().activity_collection_enabled is False


def test_runtime_initializes_state_from_persisted_settings(tmp_path) -> None:
    store = JsonStore(tmp_path)
    settings = update_settings(Settings(), "general", show_world_on_start=False)
    settings = update_settings(settings, "activity", enabled=False)
    settings = update_settings(settings, "sound", enabled=False)
    store.save_settings(settings)

    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    snapshot = runtime.snapshot()

    assert snapshot.world_visible is False
    assert snapshot.activity_collection_enabled is False
    assert snapshot.muted is True
