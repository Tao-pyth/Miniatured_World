from dataclasses import replace
import pytest
from miniatured_world.activity import ActivityAggregator, PrivacyFilter
from miniatured_world.activity.models import ActivityFrame
from miniatured_world.activity.provider import DemoActivityProvider
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.persistence import JsonStore, Settings


def run_for(window, step, duration=10000, demo=True):
    runtime = AppRuntime.start(42, provider=DemoActivityProvider() if demo else None)
    runtime.update_setting("activity", "frame_window_ms", window)
    for _ in range(duration // step):
        runtime.tick(step)
    return runtime


@pytest.mark.parametrize("window", [100, 200, 500, 1000, 1500, 5000])
@pytest.mark.parametrize("step", [100, 200, 500, 1000, 5000])
def test_same_timed_input_and_elapsed_has_same_world_at_all_heartbeat_sizes(window, step):
    expected = run_for(window, 100)
    actual = run_for(window, step)
    assert actual.service.simulation.session.state == expected.service.simulation.session.state
    assert actual.service.simulation.grid.cells == expected.service.simulation.grid.cells
    assert actual.service.simulation.session.random._random.getstate() == expected.service.simulation.session.random._random.getstate()
    assert actual.service.now_ms == expected.service.now_ms == 10000


@pytest.mark.parametrize("window", [100, 200, 1000, 5000])
def test_quiet_world_has_same_clock_at_all_windows(window):
    expected = run_for(1000, 1000, demo=False)
    actual = run_for(window, 100, demo=False)
    assert actual.service.simulation.session.state == expected.service.simulation.session.state
    assert actual.service.simulation.session.random._random.getstate() == expected.service.simulation.session.random._random.getstate()
    assert actual.snapshot().world_time == pytest.approx(8.11)


def test_events_are_consumed_once_and_future_event_waits_for_its_window():
    aggregator = ActivityAggregator(frame_window_ms=1000)
    p = PrivacyFilter()
    aggregator.add(p.keyboard("a", 1000))
    aggregator.add(p.keyboard("a", 1500))
    assert aggregator.frame(1000).keyboard_activity == 0.05
    assert aggregator.frame(2000).keyboard_activity == 0.05
    assert aggregator.frame(3000).keyboard_activity == 0
    assert not aggregator._events


def test_window_boundary_accepts_later_delivered_distinct_event_only_once():
    aggregator = ActivityAggregator()
    p = PrivacyFilter()
    aggregator.add(p.keyboard("a", 1000)); aggregator.frame(1000)
    aggregator.add(p.keyboard("b", 1000))
    assert aggregator.frame(2000).keyboard_activity == 0.05
    assert aggregator.frame(3000).keyboard_activity == 0


def test_old_event_is_discarded_without_being_replayed():
    aggregator = ActivityAggregator(frame_window_ms=100)
    aggregator.add(PrivacyFilter().keyboard("a", 10))
    assert aggregator.frame(1000).intensity() == 0
    assert not aggregator._events


@pytest.mark.parametrize("window", [100, 200, 500, 1000, 5000])
def test_activity_rates_normalize_per_second(window):
    aggregator = ActivityAggregator(frame_window_ms=window)
    # 一定レート: 20 keyboard events/second.
    for t in range(25, window, 50):
        aggregator.add(PrivacyFilter().keyboard("a", t))
    frame = aggregator.frame(window)
    assert frame.keyboard_activity == 1
    assert 0 <= frame.intensity() <= 1


def test_world_waits_for_fixed_tick_and_carries_remainder():
    runtime = AppRuntime.start(42)
    runtime.tick(700)
    assert runtime.snapshot().world_time == 0
    runtime.tick(600)
    assert runtime.snapshot().world_time == pytest.approx(0.802)
    runtime.tick(700)
    assert runtime.snapshot().world_time == pytest.approx(1.606)


def test_long_activity_window_is_used_for_its_duration_only():
    runtime = AppRuntime.start(42)
    service = runtime.service
    strong = ActivityFrame(1, 1, 1, 1, 1, 1, 0, 0)
    service._activity_windows.append((2500, strong))
    frames = [service._consume_world_frame(n * 1000) for n in range(1, 5)]
    assert [frame.keyboard_activity for frame in frames] == [1, 1, 0.5, 0]
    assert not service._activity_windows


@pytest.mark.parametrize("window", [100, 700, 1500, 5000])
def test_completed_window_backlog_is_bounded(window):
    runtime = AppRuntime.start(42, provider=DemoActivityProvider())
    runtime.update_setting("activity", "frame_window_ms", window)
    for _ in range(1000):
        runtime.tick(100)
        pending = sum(duration for duration, _ in runtime.service._activity_windows)
        assert pending < 1000 + window


def test_setting_change_applies_and_discards_all_pending_activity(tmp_path):
    runtime = AppRuntime.start(42, provider=DemoActivityProvider(), data_root=tmp_path)
    runtime.update_setting("activity", "frame_window_ms", 5000)
    runtime.tick(5000)
    assert runtime.service._activity_windows
    runtime.update_setting("activity", "frame_window_ms", 200)
    assert not runtime.service._activity_windows
    assert not runtime.service.aggregator._events
    assert runtime.service.aggregator.frame_window_ms == 200
    assert runtime.service.effective_tick_ms(1000) == 200
    restarted = AppRuntime.start(42, data_root=tmp_path)
    assert restarted.service.aggregator.frame_window_ms == 200


@pytest.mark.parametrize("control", ["off", "pause", "lock"])
def test_pause_boundaries_drop_unconsumed_window_without_resetting_world_clock(control):
    runtime = AppRuntime.start(42, provider=DemoActivityProvider())
    runtime.update_setting("activity", "frame_window_ms", 5000)
    runtime.tick(5000)
    assert runtime.service._activity_windows
    before = runtime.service.now_ms
    if control == "off": runtime.set_activity_collection(False)
    elif control == "pause": runtime.pause()
    else: runtime.set_system_suspended("lock", True)
    assert not runtime.service._activity_windows and not runtime.service.aggregator._events
    runtime.tick(4000)
    assert runtime.service.now_ms == before + (4000 if control == "off" else 0)
    runtime.set_activity_collection(True); runtime.resume(); runtime.set_system_suspended("lock", False)
    assert runtime.snapshot().activity_intensity == 0
    assert not runtime.service._activity_windows


def test_demo_event_stream_does_not_depend_on_poll_frequency():
    def sequence(step):
        provider = DemoActivityProvider()
        return [event for now in range(step, 10001, step) for event in provider.poll(now)]
    assert sequence(100) == sequence(1000) == sequence(5000)


def test_demo_does_not_invent_backlog_after_off():
    runtime = AppRuntime.start(42, provider=DemoActivityProvider())
    runtime.tick(1000)
    runtime.set_activity_collection(False); runtime.tick(8000)
    runtime.set_activity_collection(True)
    assert runtime.provider._next_cycle_ms == 10000
    events = runtime.provider.poll(10000)
    assert events and min(event.timestamp_ms for event in events) == 10000


def test_short_execution_still_saves_initial_settings_and_discovery(tmp_path):
    runtime = AppRuntime.start(42, data_root=tmp_path)
    runtime.tick(10); runtime.stop()
    assert JsonStore(tmp_path).load_settings() == Settings()
    assert (tmp_path / "settings.json").exists() and (tmp_path / "discovery.json").exists()


def test_cli_frame_budget_is_preserved_when_heartbeat_is_subdivided():
    from unittest.mock import patch
    from miniatured_world.__main__ import main
    runtime = AppRuntime.start(42)
    runtime.update_setting("activity", "frame_window_ms", 200)
    with patch("miniatured_world.__main__.AppRuntime.start", return_value=runtime):
        assert main(["--no-ui", "--activity-provider", "none", "--frames", "5", "--tick-interval-ms", "1000"]) == 0
    assert runtime.service.now_ms == 5000
    assert runtime.snapshot().world_time == pytest.approx(4.03)
