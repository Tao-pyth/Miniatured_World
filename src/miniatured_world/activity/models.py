from __future__ import annotations

from dataclasses import dataclass
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

