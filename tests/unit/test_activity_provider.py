from dataclasses import fields

import pytest

from miniatured_world.activity import (
    ActivityProviderStatus,
    ActivityType,
    DemoActivityProvider,
    NullActivityProvider,
    PointerCategory,
    WindowsIdleActivityProvider,
    WindowsGlobalActivityProvider,
    create_activity_provider,
)
from miniatured_world.activity.privacy import PrivacyFilter


def test_null_and_demo_provider_status_are_user_visible() -> None:
    stopped = NullActivityProvider().status()
    demo = DemoActivityProvider().status()

    assert stopped == ActivityProviderStatus(
        name="none",
        display_name="停止",
        available=True,
        active=False,
        detail="活動取得は停止しています。",
    )
    assert demo.name == "demo"
    assert demo.display_name == "デモ"
    assert demo.available is True
    assert demo.active is True


def test_create_activity_provider_modes() -> None:
    assert create_activity_provider("none").status().name == "none"
    assert create_activity_provider("demo").status().name == "demo"
    assert create_activity_provider("windows-idle").status().name == "windows-idle"
    assert create_activity_provider("windows-global").status().name == "windows-global"
    assert create_activity_provider("auto").status().name in {"windows-global", "windows-idle", "demo"}


def test_create_activity_provider_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="未知の活動取得元"):
        create_activity_provider("surprise")


def test_windows_idle_provider_emits_only_sanitized_idle_event() -> None:
    provider = WindowsIdleActivityProvider(
        idle_threshold_ms=1_000,
        last_input_ms=lambda: 10_000,
        clock_ms=lambda: 20_000,
    )

    events = tuple(provider.poll(30_000))

    assert provider.status().available is True
    assert len(events) == 1
    assert events[0].type == ActivityType.IDLE
    assert events[0].category == "idle"
    assert events[0].timestamp_ms == 30_000
    assert 0.0 < events[0].magnitude <= 1.0

    event_fields = {field.name for field in fields(events[0])}
    forbidden_fields = {
        "key",
        "raw",
        "text",
        "sequence",
        "x",
        "y",
        "position",
        "window_title",
        "clipboard",
        "screen",
    }
    assert event_fields.isdisjoint(forbidden_fields)


def test_windows_idle_provider_stays_quiet_below_threshold() -> None:
    provider = WindowsIdleActivityProvider(
        idle_threshold_ms=15_000,
        last_input_ms=lambda: 10_000,
        clock_ms=lambda: 20_000,
    )

    assert tuple(provider.poll(30_000)) == ()


def test_windows_idle_provider_is_unavailable_when_reader_fails() -> None:
    provider = WindowsIdleActivityProvider(last_input_ms=lambda: None, clock_ms=lambda: 20_000)

    assert provider.status().available is False
    assert tuple(provider.poll(30_000)) == ()


class _FakeWindowsBackend:
    def status(self) -> ActivityProviderStatus:
        return ActivityProviderStatus(
            name="windows-global",
            display_name="Windows実活動",
            available=True,
            active=True,
            detail="テスト用の実活動取得です。",
        )

    def poll(self, now_ms: int, privacy_filter: PrivacyFilter):
        return (
            privacy_filter.keyboard("a", now_ms),
            privacy_filter.pointer_move(120, 40, now_ms),
            privacy_filter.pointer_click(now_ms),
            privacy_filter.pointer_scroll(120, now_ms),
        )


def test_windows_global_provider_emits_only_sanitized_events() -> None:
    provider = WindowsGlobalActivityProvider(backend=_FakeWindowsBackend())

    events = tuple(provider.poll(40_000))

    assert provider.status().available is True
    assert [event.type for event in events].count(ActivityType.KEYBOARD) == 1
    assert [event.type for event in events].count(ActivityType.POINTER) == 3
    assert {event.category for event in events} >= {
        PointerCategory.MOVE.value,
        PointerCategory.CLICK.value,
        PointerCategory.SCROLL.value,
    }
    for event in events:
        event_fields = {field.name for field in fields(event)}
        forbidden_fields = {
            "key",
            "raw",
            "text",
            "sequence",
            "x",
            "y",
            "position",
            "window_title",
            "clipboard",
            "screen",
        }
        assert event_fields.isdisjoint(forbidden_fields)
