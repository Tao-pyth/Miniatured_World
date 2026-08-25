from __future__ import annotations

import math

from miniatured_world.activity.models import (
    ActivitySource,
    ActivityType,
    KeyboardCategory,
    PointerCategory,
    SanitizedActivityEvent,
)


class PrivacyFilter:
    """Converts raw-like input observations into non-reversible activity categories."""

    _MODIFIERS = {"shift", "ctrl", "control", "alt", "meta", "win", "cmd"}
    _ENTER = {"enter", "return"}
    _BACKSPACE = {"backspace", "delete", "del"}

    def keyboard(
        self,
        key_value: str,
        timestamp_ms: int,
        *,
        source: ActivitySource = ActivitySource.AMBIENT,
    ) -> SanitizedActivityEvent:
        return SanitizedActivityEvent(
            type=ActivityType.KEYBOARD,
            category=self._keyboard_category(key_value).value,
            timestamp_ms=timestamp_ms,
            magnitude=1.0,
            source=source,
        )

    def pointer_move(
        self,
        delta_x: float,
        delta_y: float,
        timestamp_ms: int,
        *,
        dragging: bool = False,
        source: ActivitySource = ActivitySource.AMBIENT,
    ) -> SanitizedActivityEvent:
        distance = math.hypot(delta_x, delta_y)
        category = PointerCategory.DRAG if dragging else PointerCategory.MOVE
        return SanitizedActivityEvent(
            type=ActivityType.POINTER,
            category=category.value,
            timestamp_ms=timestamp_ms,
            magnitude=max(0.0, min(1.0, distance / 900.0)),
            source=source,
        )

    def pointer_click(
        self,
        timestamp_ms: int,
        *,
        source: ActivitySource = ActivitySource.AMBIENT,
    ) -> SanitizedActivityEvent:
        return SanitizedActivityEvent(
            type=ActivityType.POINTER,
            category=PointerCategory.CLICK.value,
            timestamp_ms=timestamp_ms,
            magnitude=1.0,
            source=source,
        )

    def pointer_scroll(
        self,
        scroll_delta: float,
        timestamp_ms: int,
        *,
        source: ActivitySource = ActivitySource.AMBIENT,
    ) -> SanitizedActivityEvent:
        return SanitizedActivityEvent(
            type=ActivityType.POINTER,
            category=PointerCategory.SCROLL.value,
            timestamp_ms=timestamp_ms,
            magnitude=max(0.0, min(1.0, abs(scroll_delta) / 1200.0)),
            source=source,
        )

    def idle(self, timestamp_ms: int, duration_ms: int) -> SanitizedActivityEvent:
        return SanitizedActivityEvent(
            type=ActivityType.IDLE,
            category="idle",
            timestamp_ms=timestamp_ms,
            magnitude=max(0.0, min(1.0, duration_ms / 60_000.0)),
            source=ActivitySource.AMBIENT,
        )

    def _keyboard_category(self, key_value: str) -> KeyboardCategory:
        key = key_value.strip().lower()
        if key in self._MODIFIERS:
            return KeyboardCategory.MODIFIER
        if key in self._ENTER:
            return KeyboardCategory.ENTER
        if key in self._BACKSPACE:
            return KeyboardCategory.BACKSPACE
        if key_value == " " or key == "space":
            return KeyboardCategory.SPACE
        if len(key_value) == 1 and key_value.isalpha():
            return KeyboardCategory.LETTER
        if len(key_value) == 1 and key_value.isdigit():
            return KeyboardCategory.NUMBER
        if len(key_value) == 1 and not key_value.isalnum():
            return KeyboardCategory.SYMBOL
        return KeyboardCategory.OTHER

