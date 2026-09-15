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
    _next_cycle_ms: int = field(default=1000, init=False)
    _suspended: bool = field(default=False, init=False)
    _skip_backlog: bool = field(default=False, init=False)

    def reset_timing(self, now_ms: int) -> None:
        self._next_cycle_ms = (now_ms // 1000 + 1) * 1000
        self._skip_backlog = False

    def set_suspended(self, suspended: bool) -> None:
        if suspended:
            self._skip_backlog = True
        self._suspended = suspended

    def status(self) -> ActivityProviderStatus:
        return ActivityProviderStatus(
            name="demo",
            display_name="デモ",
            available=True,
            active=True,
            detail="デモ活動を生成しています。",
        )

    def poll(self, now_ms: int) -> Iterable[SanitizedActivityEvent]:
        if self._suspended:
            return ()
        if self._skip_backlog:
            self._next_cycle_ms = max(self._next_cycle_ms, ((now_ms + 999) // 1000) * 1000)
            self._skip_backlog = False
        events: list[SanitizedActivityEvent] = []
        while self._next_cycle_ms <= now_ms:
            base = self._next_cycle_ms
            cycle = base // 1000
            for offset, key in enumerate(("a", "b", "1", " ", "Enter")):
                events.append(self.privacy_filter.keyboard(key, base + offset * 30))
            events.append(self.privacy_filter.pointer_move(120 + cycle * 5, 40, base + 180))
            if cycle % 2 == 0:
                events.append(self.privacy_filter.pointer_click(base + 220))
            if cycle % 3 == 0:
                events.append(self.privacy_filter.idle(base + 300, 10_000))
            self._next_cycle_ms += 1000
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
    if normalized == "windows-global":
        from miniatured_world.activity.windows_global import WindowsGlobalActivityProvider

        return WindowsGlobalActivityProvider()
    if normalized == "auto":
        from miniatured_world.activity.windows_global import WindowsGlobalActivityProvider
        from miniatured_world.activity.windows_idle import WindowsIdleActivityProvider

        for provider in (WindowsGlobalActivityProvider(), WindowsIdleActivityProvider()):
            if provider.status().available:
                return provider
        return DemoActivityProvider()
    raise ValueError(f"未知の活動取得元です: {mode}")
