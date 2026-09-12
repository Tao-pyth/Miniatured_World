from dataclasses import replace
from itertools import permutations

import pytest

from miniatured_world.activity import ActivityProviderStatus
from miniatured_world.activity.privacy import PrivacyFilter
from miniatured_world.app.activity_startup import DeferredActivityProvider
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.persistence import JsonStore, Settings


class BufferedProvider:
    def __init__(self):
        self.suspended = False
        self.events = []
        self.polls = 0
        self.changes = []

    def status(self):
        return ActivityProviderStatus(name="test", display_name="検査用", available=True, active=not self.suspended)

    def set_suspended(self, value):
        self.suspended = value
        self.events.clear()
        self.changes.append(value)

    def poll(self, now):
        assert not self.suspended
        self.polls += 1
        events, self.events = self.events, []
        return events


@pytest.mark.parametrize("control", ["off", "pause", "stop"])
def test_stop_controls_discard_pending_input_and_preserve_world_policy(control):
    provider = BufferedProvider()
    runtime = AppRuntime.start(42, provider=provider)
    runtime.tick()
    runtime.service.aggregator.add(PrivacyFilter().keyboard("a", 1000))
    provider.events.append(PrivacyFilter().keyboard("a", 1000))
    before = runtime.snapshot().world_time
    {"off": lambda: runtime.set_activity_collection(False), "pause": runtime.pause, "stop": runtime.stop}[control]()
    assert provider.suspended and not provider.events
    assert not runtime.snapshot().provider_status.active
    assert runtime.snapshot().activity_intensity == 0
    after = runtime.tick(5000)
    assert provider.polls == 1
    assert after.world_time > before if control == "off" else after.world_time == before
    runtime.set_activity_collection(True)
    runtime.resume()
    after = runtime.tick()
    assert after.activity_intensity == 0
    assert provider.polls == (1 if control == "stop" else 2)


@pytest.mark.parametrize("release_order", list(permutations(("off", "pause", "lock"))))
def test_all_stop_reasons_must_clear_before_provider_resumes(release_order):
    provider = BufferedProvider()
    runtime = AppRuntime.start(42, provider=provider)
    runtime.set_activity_collection(False)
    runtime.pause()
    runtime.set_system_suspended("session_locked", True)
    runtime.set_system_suspended("session_locked", True)
    assert provider.changes == [False, True]
    release = {
        "off": lambda: runtime.update_setting("activity", "enabled", True),
        "pause": lambda: runtime.handle("toggle_pause"),
        "lock": lambda: runtime.set_system_suspended("session_locked", False),
    }
    for i, reason in enumerate(release_order):
        release[reason]()
        assert provider.suspended is (i < 2)
    assert provider.changes == [False, True, False]
    runtime.hide_world()
    runtime.tick()
    runtime.show_world()
    assert provider.changes == [False, True, False]


def test_initial_off_and_deferred_assignment_do_not_construct_provider(tmp_path):
    JsonStore(tmp_path).save_settings(replace(Settings(), activity=replace(Settings().activity, enabled=False)))
    made = []

    def factory():
        provider = BufferedProvider()
        made.append(provider)
        return provider

    deferred = DeferredActivityProvider(factory)
    runtime = AppRuntime.start(42, data_root=tmp_path, provider=deferred)
    deferred.poll(1000)
    runtime.tick()
    assert made == []
    runtime.set_activity_collection(True)
    runtime.tick()
    assert len(made) == 1
    runtime.pause()
    assert made[0].suspended
    runtime.resume()
    runtime.tick()
    assert len(made) == 1 and made[0].polls == 2


def test_provider_attached_while_paused_inherits_pause():
    runtime = AppRuntime.start(42)
    runtime.pause()
    provider = BufferedProvider()
    runtime.attach_provider(provider)
    assert provider.suspended
    runtime.stop()
    runtime.resume()
    runtime.set_system_suspended("session_locked", False)
    assert provider.suspended


def test_native_raw_input_parser_is_not_entered_during_manual_stop(monkeypatch):
    from miniatured_world.activity import windows_global as native

    backend = object.__new__(native._WindowsRawInputBackend)
    backend._suspended = False
    backend._hwnd = None
    backend._available = True
    backend._detail = "検査用"
    backend._queue = []
    backend._poll_timestamp_ms = 1000
    backend._pump_messages = lambda: None
    provider = native.WindowsGlobalActivityProvider(backend=backend)
    runtime = AppRuntime.start(42, provider=provider)
    monkeypatch.setattr(native, "_configure_raw_input_api", lambda _: pytest.fail("休止中にRaw Input APIへ到達"))
    for stop, resume in [(lambda: runtime.set_activity_collection(False), lambda: runtime.set_activity_collection(True)),
                         (runtime.pause, runtime.resume)]:
        stop()
        backend._handle_raw_input(0)
        assert tuple(provider.poll(2000)) == ()
        resume()
        assert backend._poll_timestamp_ms == 1000
    runtime.stop()
    backend._handle_raw_input(0)
