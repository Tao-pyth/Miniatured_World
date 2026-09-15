from dataclasses import replace
from itertools import product
from types import SimpleNamespace
from unittest.mock import Mock
import ctypes

import pytest

from miniatured_world.activity.models import ActivitySelection, ActivityFrame, ActivityType, SanitizedActivityEvent
from miniatured_world.activity.provider import NullActivityProvider
from miniatured_world.activity.privacy import PrivacyFilter
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.activity_startup import DeferredActivityProvider
from miniatured_world.persistence import JsonStore, Settings


class ArtificialProvider(NullActivityProvider):
    def poll(self, now_ms):
        return tuple(SanitizedActivityEvent(kind, category, now_ms - 100, 1.0) for kind, category in [
            (ActivityType.KEYBOARD, "letter"), (ActivityType.POINTER, "move"),
            (ActivityType.POINTER, "click"), (ActivityType.POINTER, "scroll")])


@pytest.mark.parametrize("flags", list(product([False, True], repeat=4)))
def test_category_combinations_filter_nonaware_provider_and_service(flags):
    runtime = AppRuntime.start(42, provider=ArtificialProvider())
    for field, value in zip(("keyboard_enabled", "mouse_enabled", "click_enabled", "scroll_enabled"), flags):
        runtime.update_setting("activity", field, value)
    runtime.tick()
    frame = runtime.state.last_frame
    assert tuple(v > 0 for v in (frame.keyboard_activity, frame.pointer_activity, frame.click_activity, frame.scroll_activity)) == flags
    assert runtime.snapshot().world_time > 0
    # Serviceを直接使う経路でも同じ除外境界を通る。
    service = runtime.service
    service.inject_demo_activity(0)
    direct = service.step()
    assert flags[0] or direct.keyboard_activity == 0
    assert flags[1] or direct.pointer_activity == 0
    assert flags[2] or direct.click_activity == 0
    assert flags[3] or direct.scroll_activity == 0


def test_selection_keeps_idle_and_excludes_direct_activity():
    from miniatured_world.activity import ActivityAggregator, ActivitySource
    aggregator = ActivityAggregator(selection=ActivitySelection(False, False, False, False))
    privacy = PrivacyFilter()
    aggregator.add(privacy.idle(500, 15000))
    aggregator.add(privacy.keyboard("a", 600, source=ActivitySource.DIRECT))
    frame = aggregator.frame(1000)
    assert frame.intensity() == 0 and frame.idle_ratio == 1


def test_selection_applies_on_restart_and_before_deferred_first_poll(tmp_path):
    settings = replace(Settings(), activity=replace(Settings().activity, keyboard_enabled=False, click_enabled=False))
    JsonStore(tmp_path).save_settings(settings)
    made = []
    class AwareProvider(ArtificialProvider):
        def set_selection(self, selection): self.selection = selection
        def poll(self, now):
            assert self.selection == ActivitySelection(False, True, False, True)
            return super().poll(now)
    def factory():
        provider = AwareProvider(); made.append(provider); return provider
    runtime = AppRuntime.start(42, provider=DeferredActivityProvider(factory), data_root=tmp_path)
    assert not made
    runtime.tick()
    assert len(made) == 1
    assert runtime.state.last_frame.keyboard_activity == runtime.state.last_frame.click_activity == 0


@pytest.mark.parametrize("pause", ["manual", "system", "off"])
def test_selection_change_does_not_resume_paused_provider_or_replay_queue(pause):
    class Buffered(NullActivityProvider):
        def __init__(self): self.pending = []; self.suspended = False
        def set_suspended(self, value): self.suspended = value; self.pending.clear()
        def poll(self, now):
            assert not self.suspended
            pending, self.pending = self.pending, []
            return pending
    provider = Buffered(); runtime = AppRuntime.start(42, provider=provider)
    provider.pending.append(PrivacyFilter().keyboard("a", 500))
    runtime.service.aggregator.add(PrivacyFilter().keyboard("a", 500))
    runtime.update_setting("activity", "keyboard_enabled", False)
    assert not provider.pending
    if pause == "manual": runtime.pause()
    elif pause == "system": runtime.set_system_suspended("lock", True)
    else: runtime.set_activity_collection(False)
    runtime.update_setting("activity", "keyboard_enabled", True)
    assert provider.suspended
    runtime.tick()
    runtime.resume(); runtime.set_system_suspended("lock", False); runtime.set_activity_collection(True)
    assert runtime.tick().activity_intensity == 0


@pytest.mark.parametrize("strength", [0.0, 0.5, 1.0, -1.0, 2.0])
def test_strength_is_quiet_interpolation_without_changing_session_time(strength):
    frame = ActivityFrame(0.8, 0.6, 0.4, 0.2, 0.7, 0.9, 0.3, 20)
    result = frame.with_strength(strength)
    factor = max(0, min(1, strength))
    assert result.keyboard_activity == frame.keyboard_activity * factor
    assert result.pointer_activity == frame.pointer_activity * factor
    assert result.click_activity == frame.click_activity * factor
    assert result.scroll_activity == frame.scroll_activity * factor
    assert result.burstiness == frame.burstiness * factor
    assert result.continuity == frame.continuity * factor
    assert result.idle_ratio == pytest.approx(1 - 0.7 * factor)
    assert result.session_duration == 20
    if strength == 0: assert result == ActivityFrame.quiet(session_duration=20)
    if strength == 1: assert result is frame


def test_strength_zero_has_same_world_as_quiet_without_stopping_collection():
    from miniatured_world.world import WorldSession, WorldSimulation
    runtime = AppRuntime.start(42, provider=ArtificialProvider())
    runtime.update_setting("activity", "reflection_strength", 0.0)
    runtime.tick()
    expected = WorldSimulation(WorldSession.create(42))
    expected.step(ActivityFrame.quiet(runtime.state.last_frame.session_duration))
    assert runtime.service.simulation.summary() == expected.summary()
    assert runtime.snapshot().activity_intensity == 0
    assert runtime.state.activity_collection_enabled


def make_backend():
    from miniatured_world.activity.windows_global import _WindowsRawInputBackend
    backend = object.__new__(_WindowsRawInputBackend)
    backend._selection = ActivitySelection()
    backend._suspended = False; backend._hwnd = None; backend._available = True
    backend._detail = "test"; backend._queue = []; backend._poll_timestamp_ms = 1000
    backend._privacy_filter = PrivacyFilter(); backend._pump_messages = lambda: None
    return backend


def test_native_all_off_does_not_reach_raw_api(monkeypatch):
    from miniatured_world.activity import windows_global as native
    backend = make_backend(); backend.set_selection(ActivitySelection(False, False, False, False))
    monkeypatch.setattr(native, "_configure_raw_input_api", lambda _: pytest.fail("Raw API reached"))
    backend._handle_raw_input(0)
    assert not backend._queue and not backend.status().active


@pytest.mark.parametrize("device", [0, 1])
def test_native_disabled_device_reads_header_only(device, monkeypatch):
    from miniatured_world.activity import windows_global as native
    backend = make_backend()
    backend.set_selection(ActivitySelection(device == 0, device == 1, device == 1, device == 1))
    calls = []
    def read(handle, command, buffer, size, header_size):
        calls.append(command)
        assert command == 0x10000005
        ctypes.cast(buffer, ctypes.POINTER(native._RAWINPUTHEADER)).contents.dwType = device
        return header_size
    monkeypatch.setattr(native.ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(GetRawInputData=read)))
    monkeypatch.setattr(native, "_configure_raw_input_api", lambda _: None)
    backend._handle_raw_input(0)
    assert calls == [0x10000005] and not backend._queue


@pytest.mark.parametrize("flags", list(product([False, True], repeat=3)))
def test_native_mouse_converts_only_selected_fields(flags):
    from miniatured_world.activity import windows_global as native
    backend = make_backend(); backend.set_selection(ActivitySelection(True, *flags))
    mouse = native._RAWMOUSE(); mouse.lLastX = 10; mouse.lLastY = 5
    mouse.button_union.buttons.usButtonFlags = 0x0401
    mouse.button_union.buttons.usButtonData = 120
    privacy = Mock(wraps=PrivacyFilter())
    backend._mouse_events(mouse, 1000, privacy)
    assert tuple(getattr(privacy, method).call_count > 0 for method in ("pointer_move", "pointer_click", "pointer_scroll")) == flags


def test_native_disabled_keyboard_and_mouse_never_access_payload_fields():
    backend = make_backend(); backend.set_selection(ActivitySelection(False, False, False, False))
    assert backend._keyboard_event(object(), 1000, PrivacyFilter()) is None
    assert backend._mouse_events(object(), 1000, PrivacyFilter()) == ()


@pytest.mark.parametrize("device,selection,header_expected", [
    (1, ActivitySelection(True, False, False, False), True),
    (0, ActivitySelection(False, True, True, True), True),
    (1, ActivitySelection(), False),
])
def test_native_enabled_device_still_reads_body(device, selection, header_expected, monkeypatch):
    from miniatured_world.activity import windows_global as native
    backend = make_backend(); backend.set_selection(selection)
    packet = native._RAWINPUT(); packet.header.dwType = device
    packet.data.keyboard.Message = 0x0100; packet.data.keyboard.VKey = 0x41
    if device == 0:
        packet.data.mouse.lLastX = 10
        packet.data.mouse.button_union.buttons.usButtonFlags = 0
    calls = []
    def read(handle, command, buffer, size, header_size):
        calls.append(command)
        if command == 0x10000005:
            ctypes.cast(buffer, ctypes.POINTER(native._RAWINPUTHEADER)).contents.dwType = device
            return header_size
        if buffer is None:
            ctypes.cast(size, ctypes.POINTER(ctypes.c_uint)).contents.value = ctypes.sizeof(packet)
            return 0
        ctypes.memmove(buffer, ctypes.byref(packet), ctypes.sizeof(packet))
        return ctypes.sizeof(packet)
    monkeypatch.setattr(native.ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(GetRawInputData=read)))
    monkeypatch.setattr(native, "_configure_raw_input_api", lambda _: None)
    backend._handle_raw_input(0)
    assert calls == ([0x10000005] if header_expected else []) + [0x10000003, 0x10000003]
    assert backend._queue
    assert backend._queue[0].type == (ActivityType.KEYBOARD if device == 1 else ActivityType.POINTER)


@pytest.mark.parametrize("result", [0, 1, 0xFFFFFFFF])
def test_bad_header_never_fetches_body(result, monkeypatch):
    from miniatured_world.activity import windows_global as native
    backend = make_backend(); backend.set_selection(ActivitySelection(False, True, True, True))
    read = Mock(return_value=result)
    monkeypatch.setattr(native.ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(GetRawInputData=read)))
    monkeypatch.setattr(native, "_configure_raw_input_api", lambda _: None)
    backend._handle_raw_input(0)
    assert read.call_count == 1 and not backend._queue
