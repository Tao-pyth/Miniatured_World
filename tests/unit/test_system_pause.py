import pytest

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.activity.privacy import PrivacyFilter
from miniatured_world.activity.windows_global import _WindowsRawInputBackend
from miniatured_world.app.activity_startup import DeferredActivityProvider
from miniatured_world.app.runtime import AppRuntime


@pytest.mark.parametrize("manual,activity,visible", [(False, True, True), (True, True, True), (False, False, True), (False, True, False)])
def test_system_pause_freezes_world_without_changing_user_controls(manual, activity, visible):
    runtime = AppRuntime.start(seed=42, provider=DemoActivityProvider())
    runtime.tick()
    runtime.state.paused = manual
    runtime.set_activity_collection(activity)
    runtime.state.world_visible = visible
    simulation = runtime.service.simulation
    before = runtime.snapshot()
    clock = runtime.service.now_ms
    runtime.set_system_suspended("session_locked", True)
    for _ in range(5):
        assert runtime.tick(60_000).world_time == before.world_time
    assert runtime.service.now_ms == clock
    assert runtime.snapshot().system_paused
    assert not runtime.snapshot().provider_status.active
    runtime.set_system_suspended("session_locked", False)
    assert runtime.state.paused == manual
    assert runtime.state.activity_collection_enabled == activity
    assert runtime.state.world_visible == visible
    assert runtime.service.simulation is simulation
    after = runtime.tick()
    assert after.seed == before.seed
    assert after.world_time == before.world_time if manual else after.world_time > before.world_time
    assert runtime.service.now_ms == clock + (0 if manual else 1000)


def test_overlapping_reasons_and_duplicate_notifications_do_not_resume_early():
    runtime = AppRuntime.start(seed=42)
    for reason in ("session_locked", "session_locked", "system_sleep"):
        runtime.set_system_suspended(reason, True)
    runtime.set_system_suspended("system_sleep", False)
    runtime.resume()
    assert runtime.tick().world_time == 0
    runtime.stop()
    runtime.set_system_suspended("session_locked", False)
    assert runtime.tick().world_time == 0
    assert not runtime.state.running


def test_system_pause_does_not_construct_deferred_provider():
    calls = []
    provider = DeferredActivityProvider(lambda: calls.append(True))
    runtime = AppRuntime.start(seed=42, provider=provider)
    runtime.set_system_suspended("session_locked", True)
    runtime.tick()
    runtime.set_system_suspended("session_locked", False)
    assert calls == []


def test_suspend_discards_aggregated_and_native_pending_input(monkeypatch):
    backend = object.__new__(_WindowsRawInputBackend)
    backend._suspended = False
    backend._available = True
    backend._hwnd = 123
    backend._poll_timestamp_ms = 30
    backend._queue = [PrivacyFilter().keyboard("a", 1000)]
    # 無効な生入力ポインターを解釈せず返ることも検証する。
    backend._pump_messages = lambda: backend._handle_raw_input(0)
    backend.set_suspended(True)
    assert backend._queue == []
    assert tuple(backend.poll(2000, PrivacyFilter())) == ()
    backend.set_suspended(False)
    assert backend._poll_timestamp_ms == 30
    assert not backend._suspended
    runtime = AppRuntime.start(seed=42)
    runtime.service.aggregator.add(PrivacyFilter().keyboard("a", 1000))
    runtime.set_system_suspended("session_locked", True)
    runtime.set_system_suspended("session_locked", False)
    assert runtime.tick().activity_intensity == 0
