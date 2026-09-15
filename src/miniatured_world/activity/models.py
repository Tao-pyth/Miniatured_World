from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum


class ActivityType(StrEnum):
    KEYBOARD = "keyboard"
    POINTER = "pointer"
    IDLE = "idle"


class ActivitySource(StrEnum):
    AMBIENT = "ambient"
    DIRECT = "direct"


class KeyboardCategory(StrEnum):
    LETTER = "letter"
    NUMBER = "number"
    SYMBOL = "symbol"
    SPACE = "space"
    ENTER = "enter"
    BACKSPACE = "backspace"
    MODIFIER = "modifier"
    OTHER = "other"


class PointerCategory(StrEnum):
    MOVE = "move"
    CLICK = "click"
    SCROLL = "scroll"
    DRAG = "drag"


@dataclass(frozen=True, slots=True)
class SanitizedActivityEvent:
    """Privacy-safe activity event. It intentionally has no raw key or coordinate fields."""

    type: ActivityType
    category: str
    timestamp_ms: int
    magnitude: float = 1.0
    source: ActivitySource = ActivitySource.AMBIENT

    def normalized_magnitude(self) -> float:
        return max(0.0, min(1.0, self.magnitude))


@dataclass(frozen=True, slots=True)
class ActivitySelection:
    keyboard: bool = True
    movement: bool = True
    click: bool = True
    scroll: bool = True

    @property
    def any_pointer(self) -> bool:
        return self.movement or self.click or self.scroll

    @property
    def any_enabled(self) -> bool:
        return self.keyboard or self.any_pointer

    def allows(self, event: SanitizedActivityEvent) -> bool:
        if event.type == ActivityType.KEYBOARD:
            return self.keyboard
        if event.type == ActivityType.POINTER:
            return {
                PointerCategory.MOVE.value: self.movement,
                PointerCategory.DRAG.value: self.movement,
                PointerCategory.CLICK.value: self.click,
                PointerCategory.SCROLL.value: self.scroll,
            }.get(event.category, False)
        return event.type == ActivityType.IDLE


@dataclass(frozen=True, slots=True)
class ActivityFrame:
    keyboard_activity: float
    pointer_activity: float
    click_activity: float
    scroll_activity: float
    burstiness: float
    continuity: float
    idle_ratio: float
    session_duration: float

    @classmethod
    def quiet(cls, session_duration: float = 0.0) -> "ActivityFrame":
        return cls(
            keyboard_activity=0.0,
            pointer_activity=0.0,
            click_activity=0.0,
            scroll_activity=0.0,
            burstiness=0.0,
            continuity=0.0,
            idle_ratio=1.0,
            session_duration=session_duration,
        )

    def with_strength(self, strength: float) -> "ActivityFrame":
        amount = max(0.0, min(1.0, strength))
        if amount == 1.0:
            return self
        return replace(
            self,
            keyboard_activity=self.keyboard_activity * amount,
            pointer_activity=self.pointer_activity * amount,
            click_activity=self.click_activity * amount,
            scroll_activity=self.scroll_activity * amount,
            burstiness=self.burstiness * amount,
            continuity=self.continuity * amount,
            idle_ratio=1.0 - (1.0 - self.idle_ratio) * amount,
        )

    def intensity(self) -> float:
        active = (
            self.keyboard_activity * 0.42
            + self.pointer_activity * 0.24
            + self.click_activity * 0.14
            + self.scroll_activity * 0.08
            + self.burstiness * 0.07
            + self.continuity * 0.05
        )
        return max(0.0, min(1.0, active))

