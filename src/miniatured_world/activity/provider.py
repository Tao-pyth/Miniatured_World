from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

from miniatured_world.activity.models import SanitizedActivityEvent
from miniatured_world.activity.privacy import PrivacyFilter


@dataclass(frozen=True, slots=True)
class ActivityProviderStatus:
    name: str
    display_name: str
    available: bool
    active: bool
    detail: str = ""


class ActivityProvider(Protocol):
    def poll(self, now_ms: int) -> Iterable[SanitizedActivityEvent]:
        """サニタイズ済み活動イベントだけを返す。"""

    def status(self) -> ActivityProviderStatus:
        """Raw Inputを露出せず、ユーザー向けの取得状態だけを返す。"""


@dataclass(slots=True)
class NullActivityProvider:
    def poll(self, now_ms: int) -> Iterable[SanitizedActivityEvent]:
        return ()

    def status(self) -> ActivityProviderStatus:
        return ActivityProviderStatus(
            name="none",
            display_name="停止",
            available=True,
            active=False,
            detail="活動取得は停止しています。",
        )


@dataclass(slots=True)
class DemoActivityProvider:
    privacy_filter: PrivacyFilter = field(default_factory=PrivacyFilter)

    def status(self) -> ActivityProviderStatus:
        return ActivityProviderStatus(
            name="demo",
            display_name="デモ",
            available=True,
            active=True,
            detail="デモ活動を生成しています。",
        )

    def poll(self, now_ms: int) -> Iterable[SanitizedActivityEvent]:
        cycle = max(0, now_ms // 1000)
        events: list[SanitizedActivityEvent] = []
        for offset, key in enumerate(("a", "b", "1", " ", "Enter")):
            events.append(self.privacy_filter.keyboard(key, now_ms + offset * 30))
        events.append(self.privacy_filter.pointer_move(120 + cycle * 5, 40, now_ms + 180))
        if cycle % 2 == 0:
            events.append(self.privacy_filter.pointer_click(now_ms + 220))
        if cycle % 3 == 0:
            events.append(self.privacy_filter.idle(now_ms + 300, 10_000))
        return tuple(events)


def create_activity_provider(mode: str = "auto") -> ActivityProvider:
    normalized = mode.strip().lower().replace("_", "-")
    if normalized == "none":
        return NullActivityProvider()
    if normalized == "demo":
        return DemoActivityProvider()
    if normalized == "windows-idle":
        from miniatured_world.activity.windows_idle import WindowsIdleActivityProvider

        return WindowsIdleActivityProvider()
    if normalized == "auto":
        from miniatured_world.activity.windows_idle import WindowsIdleActivityProvider

        provider = WindowsIdleActivityProvider()
        if provider.status().available:
            return provider
        return DemoActivityProvider()
    raise ValueError(f"未知の活動取得元です: {mode}")
