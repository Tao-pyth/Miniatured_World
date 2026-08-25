from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

from miniatured_world.activity.models import SanitizedActivityEvent
from miniatured_world.activity.privacy import PrivacyFilter


class ActivityProvider(Protocol):
    def poll(self, now_ms: int) -> Iterable[SanitizedActivityEvent]:
        """Return already-sanitized activity events."""


@dataclass(slots=True)
class NullActivityProvider:
    def poll(self, now_ms: int) -> Iterable[SanitizedActivityEvent]:
        return ()


@dataclass(slots=True)
class DemoActivityProvider:
    privacy_filter: PrivacyFilter = field(default_factory=PrivacyFilter)

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
