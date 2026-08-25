from __future__ import annotations

import ctypes
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from miniatured_world.activity.models import SanitizedActivityEvent
from miniatured_world.activity.privacy import PrivacyFilter
from miniatured_world.activity.provider import ActivityProviderStatus


LastInputReader = Callable[[], int | None]
ClockReader = Callable[[], int]


@dataclass(slots=True)
class WindowsIdleActivityProvider:
    privacy_filter: PrivacyFilter = field(default_factory=PrivacyFilter)
    idle_threshold_ms: int = 15_000
    last_input_ms: LastInputReader | None = None
    clock_ms: ClockReader | None = None
    _available: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        if self.last_input_ms is None:
            self.last_input_ms = _windows_last_input_ms
        if self.clock_ms is None:
            self.clock_ms = _windows_tick_ms if sys.platform == "win32" else _monotonic_ms
        self._available = self._read_last_input_ms() is not None

    def status(self) -> ActivityProviderStatus:
        if not self._available:
            return ActivityProviderStatus(
                name="windows-idle",
                display_name="WindowsアイドルPoC",
                available=False,
                active=False,
                detail="この環境ではWindowsアイドル取得を利用できません。",
            )
        return ActivityProviderStatus(
            name="windows-idle",
            display_name="WindowsアイドルPoC",
            available=True,
            active=True,
            detail="Windowsの最終入力時刻からアイドル時間だけを取得しています。",
        )

    def poll(self, now_ms: int) -> Iterable[SanitizedActivityEvent]:
        if not self._available:
            return ()

        last_input = self._read_last_input_ms()
        if last_input is None:
            self._available = False
            return ()

        idle_duration_ms = max(0, self._clock_ms() - last_input)
        if idle_duration_ms < self.idle_threshold_ms:
            return ()
        return (self.privacy_filter.idle(now_ms, idle_duration_ms),)

    def _read_last_input_ms(self) -> int | None:
        try:
            return self.last_input_ms()
        except OSError:
            return None

    def _clock_ms(self) -> int:
        try:
            return int(self.clock_ms())
        except OSError:
            return _monotonic_ms()


def _monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


def _windows_tick_ms() -> int:
    if sys.platform != "win32":
        return _monotonic_ms()
    return int(ctypes.windll.kernel32.GetTickCount())


def _windows_last_input_ms() -> int | None:
    if sys.platform != "win32":
        return None

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("dwTime", ctypes.c_uint),
        ]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return None
    return int(info.dwTime)
