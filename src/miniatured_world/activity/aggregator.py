from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from miniatured_world.activity.models import (
    ActivityFrame,
    ActivitySource,
    ActivityType,
    PointerCategory,
    SanitizedActivityEvent,
)


@dataclass(slots=True)
class ActivityAggregator:
    frame_window_ms: int = 1000
    _events: list[SanitizedActivityEvent] = field(default_factory=list)
    _session_start_ms: int | None = None

    def add(self, event: SanitizedActivityEvent) -> None:
        if event.source == ActivitySource.DIRECT:
            return
        self._events.append(event)
        if self._session_start_ms is None:
            self._session_start_ms = event.timestamp_ms

    def frame(self, now_ms: int) -> ActivityFrame:
        if self._session_start_ms is None:
            self._session_start_ms = now_ms

        start_ms = now_ms - self.frame_window_ms
        window_events = [event for event in self._events if start_ms <= event.timestamp_ms <= now_ms]
        self._events = [event for event in self._events if event.timestamp_ms > start_ms]
        session_duration = max(0.0, (now_ms - self._session_start_ms) / 1000.0)

        if not window_events:
            return ActivityFrame.quiet(session_duration=session_duration)

        by_type = Counter(event.type for event in window_events)
        by_pointer = Counter(event.category for event in window_events if event.type == ActivityType.POINTER)
        pointer_magnitude = sum(
            event.normalized_magnitude()
            for event in window_events
            if event.type == ActivityType.POINTER
            and event.category in {PointerCategory.MOVE.value, PointerCategory.DRAG.value}
        )
        scroll_magnitude = sum(
            event.normalized_magnitude()
            for event in window_events
            if event.type == ActivityType.POINTER and event.category == PointerCategory.SCROLL.value
        )
        idle_magnitude = sum(
            event.normalized_magnitude()
            for event in window_events
            if event.type == ActivityType.IDLE
        )

        active_event_count = by_type[ActivityType.KEYBOARD] + by_type[ActivityType.POINTER]
        keyboard_activity = min(1.0, by_type[ActivityType.KEYBOARD] / 20.0)
        pointer_activity = min(1.0, pointer_magnitude / 5.0)
        click_activity = min(1.0, by_pointer[PointerCategory.CLICK.value] / 8.0)
        scroll_activity = min(1.0, scroll_magnitude / 4.0)
        burstiness = self._burstiness(window_events)
        continuity = min(1.0, self._active_bucket_count(window_events, start_ms) / 5.0)

        active = min(1.0, active_event_count / 30.0 + pointer_activity * 0.25)
        idle_ratio = max(0.0, min(1.0, max(idle_magnitude, 1.0 - active)))

        return ActivityFrame(
            keyboard_activity=keyboard_activity,
            pointer_activity=pointer_activity,
            click_activity=click_activity,
            scroll_activity=scroll_activity,
            burstiness=burstiness,
            continuity=continuity,
            idle_ratio=idle_ratio,
            session_duration=session_duration,
        )

    def _burstiness(self, events: list[SanitizedActivityEvent]) -> float:
        bucket_counts: Counter[int] = Counter(event.timestamp_ms // 200 for event in events)
        return min(1.0, max(bucket_counts.values(), default=0) / 8.0)

    def _active_bucket_count(self, events: list[SanitizedActivityEvent], start_ms: int) -> int:
        return len({max(0, event.timestamp_ms - start_ms) // 200 for event in events})

