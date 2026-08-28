from __future__ import annotations

import ctypes
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

from miniatured_world.activity.models import SanitizedActivityEvent
from miniatured_world.activity.privacy import PrivacyFilter
from miniatured_world.activity.provider import ActivityProviderStatus


class WindowsActivityBackend(Protocol):
    def status(self) -> ActivityProviderStatus:
        """ユーザー向けの取得状態だけを返す。"""

    def poll(self, now_ms: int, privacy_filter: PrivacyFilter) -> Iterable[SanitizedActivityEvent]:
        """サニタイズ済み活動イベントだけを返す。"""


class _RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", ctypes.c_ushort),
        ("usUsage", ctypes.c_ushort),
        ("dwFlags", ctypes.c_uint),
        ("hwndTarget", ctypes.c_void_p),
    ]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_uint),
        ("pt", _POINT),
    ]


class _RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", ctypes.c_uint),
        ("dwSize", ctypes.c_uint),
        ("hDevice", ctypes.c_void_p),
        ("wParam", ctypes.c_size_t),
    ]


class _RAWMOUSE_BUTTONS(ctypes.Structure):
    _fields_ = [("usButtonFlags", ctypes.c_ushort), ("usButtonData", ctypes.c_ushort)]


class _RAWMOUSE_BUTTON_UNION(ctypes.Union):
    _fields_ = [("ulButtons", ctypes.c_uint), ("buttons", _RAWMOUSE_BUTTONS)]


class _RAWMOUSE(ctypes.Structure):
    _fields_ = [
        ("usFlags", ctypes.c_ushort),
        ("button_union", _RAWMOUSE_BUTTON_UNION),
        ("ulRawButtons", ctypes.c_uint),
        ("lLastX", ctypes.c_long),
        ("lLastY", ctypes.c_long),
        ("ulExtraInformation", ctypes.c_uint),
    ]


class _RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", ctypes.c_ushort),
        ("Flags", ctypes.c_ushort),
        ("Reserved", ctypes.c_ushort),
        ("VKey", ctypes.c_ushort),
        ("Message", ctypes.c_uint),
        ("ExtraInformation", ctypes.c_uint),
    ]


class _RAWHID(ctypes.Structure):
    _fields_ = [
        ("dwSizeHid", ctypes.c_uint),
        ("dwCount", ctypes.c_uint),
        ("bRawData", ctypes.c_ubyte * 1),
    ]


class _RAWINPUT_UNION(ctypes.Union):
    _fields_ = [("mouse", _RAWMOUSE), ("keyboard", _RAWKEYBOARD), ("hid", _RAWHID)]


class _RAWINPUT(ctypes.Structure):
    _fields_ = [("header", _RAWINPUTHEADER), ("data", _RAWINPUT_UNION)]


_MESSAGE_API_CONFIGURED = False
_RAW_INPUT_API_CONFIGURED = False


@dataclass(slots=True)
class WindowsGlobalActivityProvider:
    privacy_filter: PrivacyFilter = field(default_factory=PrivacyFilter)
    backend: WindowsActivityBackend | None = None

    def __post_init__(self) -> None:
        if self.backend is None:
            self.backend = _WindowsRawInputBackend()

    def status(self) -> ActivityProviderStatus:
        return self.backend.status()

    def poll(self, now_ms: int) -> Iterable[SanitizedActivityEvent]:
        if not self.backend.status().active:
            return ()
        return tuple(self.backend.poll(now_ms, self.privacy_filter))


@dataclass(slots=True)
class _UnavailableWindowsBackend:
    detail: str

    def status(self) -> ActivityProviderStatus:
        return ActivityProviderStatus(
            name="windows-global",
            display_name="Windows実活動",
            available=False,
            active=False,
            detail=self.detail,
        )

    def poll(self, now_ms: int, privacy_filter: PrivacyFilter) -> Iterable[SanitizedActivityEvent]:
        return ()


class _WindowsRawInputBackend:
    def __init__(self) -> None:
        self._queue: list[SanitizedActivityEvent] = []
        self._poll_timestamp_ms = 0
        self._privacy_filter = PrivacyFilter()
        self._hwnd: int | None = None
        self._wndproc = None
        self._available = False
        self._detail = "この環境ではWindows実活動取得を利用できません。"
        if sys.platform != "win32":
            return
        try:
            self._setup_window()
            self._register_raw_input_devices()
        except OSError as error:
            self._detail = f"Windows実活動取得の初期化に失敗しました: {error}"
            self._destroy_window()
            return
        self._available = True
        self._detail = "Raw Inputを即時カテゴリ化し、実入力内容や座標を保存せずに活動取得しています。"

    def status(self) -> ActivityProviderStatus:
        return ActivityProviderStatus(
            name="windows-global",
            display_name="Windows実活動",
            available=self._available,
            active=self._available,
            detail=self._detail,
        )

    def poll(self, now_ms: int, privacy_filter: PrivacyFilter) -> Iterable[SanitizedActivityEvent]:
        if not self._available:
            return ()
        self._poll_timestamp_ms = now_ms
        self._privacy_filter = privacy_filter
        self._pump_messages()
        events = tuple(self._queue)
        self._queue.clear()
        return events

    def _setup_window(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        class_name = "MiniaturedWorldRawInputWindow"

        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        )

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", ctypes.c_uint),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.c_void_p),
                ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p),
                ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", ctypes.c_wchar_p),
                ("lpszClassName", ctypes.c_wchar_p),
            ]

        kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
        user32.RegisterClassW.restype = ctypes.c_ushort
        user32.CreateWindowExW.argtypes = [
            ctypes.c_uint,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        user32.CreateWindowExW.restype = ctypes.c_void_p
        user32.DefWindowProcW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        ]
        user32.DefWindowProcW.restype = ctypes.c_ssize_t

        hinstance = kernel32.GetModuleHandleW(None)
        self._wndproc = WNDPROC(self._window_proc)
        wndclass = WNDCLASSW(
            0,
            self._wndproc,
            0,
            0,
            hinstance,
            None,
            None,
            None,
            None,
            class_name,
        )
        atom = user32.RegisterClassW(ctypes.byref(wndclass))
        if atom == 0 and ctypes.GetLastError() != 1410:
            raise ctypes.WinError()

        hwnd = user32.CreateWindowExW(
            0,
            class_name,
            "Miniatured World Raw Input",
            0,
            0,
            0,
            0,
            0,
            None,
            None,
            hinstance,
            None,
        )
        if not hwnd:
            raise ctypes.WinError()
        self._hwnd = int(hwnd)

    def _register_raw_input_devices(self) -> None:
        if self._hwnd is None:
            raise OSError("Raw Input window is not initialized.")

        RIDEV_INPUTSINK = 0x00000100
        devices = (_RAWINPUTDEVICE * 2)(
            _RAWINPUTDEVICE(0x01, 0x06, RIDEV_INPUTSINK, self._hwnd),
            _RAWINPUTDEVICE(0x01, 0x02, RIDEV_INPUTSINK, self._hwnd),
        )
        ctypes.windll.user32.RegisterRawInputDevices.argtypes = [
            ctypes.POINTER(_RAWINPUTDEVICE),
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        ctypes.windll.user32.RegisterRawInputDevices.restype = ctypes.c_int
        ok = ctypes.windll.user32.RegisterRawInputDevices(
            devices,
            len(devices),
            ctypes.sizeof(_RAWINPUTDEVICE),
        )
        if not ok:
            raise ctypes.WinError()

    def _pump_messages(self) -> None:
        user32 = ctypes.windll.user32
        msg = _MSG()
        PM_REMOVE = 0x0001
        _configure_message_api(user32)
        while user32.PeekMessageW(ctypes.byref(msg), self._hwnd, 0, 0, PM_REMOVE):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _window_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        WM_INPUT = 0x00FF
        if msg == WM_INPUT:
            self._handle_raw_input(lparam)
            return int(ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam))
        return int(ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam))

    def _handle_raw_input(self, lparam: int) -> None:
        RID_INPUT = 0x10000003
        RIM_TYPEMOUSE = 0
        RIM_TYPEKEYBOARD = 1
        user32 = ctypes.windll.user32
        size = ctypes.c_uint(0)
        header_size = ctypes.sizeof(_RAWINPUTHEADER)
        _configure_raw_input_api(user32)
        user32.GetRawInputData(lparam, RID_INPUT, None, ctypes.byref(size), header_size)
        if size.value == 0:
            return
        buffer = ctypes.create_string_buffer(size.value)
        read_size = user32.GetRawInputData(lparam, RID_INPUT, buffer, ctypes.byref(size), header_size)
        if read_size != size.value:
            return

        raw_input = ctypes.cast(buffer, ctypes.POINTER(_RAWINPUT)).contents
        timestamp = self._poll_timestamp_ms or _monotonic_ms()
        if raw_input.header.dwType == RIM_TYPEKEYBOARD:
            event = self._keyboard_event(raw_input.data.keyboard, timestamp, self._privacy_filter)
            if event is not None:
                self._queue.append(event)
        elif raw_input.header.dwType == RIM_TYPEMOUSE:
            self._queue.extend(self._mouse_events(raw_input.data.mouse, timestamp, self._privacy_filter))

    def _keyboard_event(
        self,
        keyboard,
        timestamp_ms: int,
        privacy_filter: PrivacyFilter,
    ) -> SanitizedActivityEvent | None:
        WM_KEYDOWN = 0x0100
        WM_SYSKEYDOWN = 0x0104
        if int(keyboard.Message) not in {WM_KEYDOWN, WM_SYSKEYDOWN}:
            return None
        key_value = _vkey_to_key_value(int(keyboard.VKey))
        return privacy_filter.keyboard(key_value, timestamp_ms)

    def _mouse_events(
        self,
        mouse,
        timestamp_ms: int,
        privacy_filter: PrivacyFilter,
    ) -> tuple[SanitizedActivityEvent, ...]:
        events: list[SanitizedActivityEvent] = []
        delta_x = float(mouse.lLastX)
        delta_y = float(mouse.lLastY)
        if delta_x or delta_y:
            events.append(privacy_filter.pointer_move(delta_x, delta_y, timestamp_ms))

        flags = int(mouse.button_union.buttons.usButtonFlags)
        button_data = int(mouse.button_union.buttons.usButtonData)
        click_flags = {0x0001, 0x0004, 0x0010, 0x0040, 0x0100}
        if any(flags & flag for flag in click_flags):
            events.append(privacy_filter.pointer_click(timestamp_ms))
        if flags & 0x0400 or flags & 0x0800:
            events.append(privacy_filter.pointer_scroll(_signed_ushort(button_data), timestamp_ms))
        return tuple(events)

    def _destroy_window(self) -> None:
        if self._hwnd:
            ctypes.windll.user32.DestroyWindow(self._hwnd)
            self._hwnd = None

    def __del__(self) -> None:
        if sys.platform == "win32":
            self._destroy_window()


def _signed_ushort(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def _monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


def _configure_message_api(user32) -> None:
    global _MESSAGE_API_CONFIGURED
    if _MESSAGE_API_CONFIGURED:
        return

    user32.PeekMessageW.argtypes = [
        ctypes.POINTER(_MSG),
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_uint,
    ]
    user32.PeekMessageW.restype = ctypes.c_int
    user32.TranslateMessage.argtypes = [ctypes.POINTER(_MSG)]
    user32.TranslateMessage.restype = ctypes.c_int
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(_MSG)]
    user32.DispatchMessageW.restype = ctypes.c_ssize_t
    _MESSAGE_API_CONFIGURED = True


def _configure_raw_input_api(user32) -> None:
    global _RAW_INPUT_API_CONFIGURED
    if _RAW_INPUT_API_CONFIGURED:
        return

    user32.GetRawInputData.argtypes = [
        ctypes.c_ssize_t,
        ctypes.c_uint,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint),
        ctypes.c_uint,
    ]
    user32.GetRawInputData.restype = ctypes.c_uint
    _RAW_INPUT_API_CONFIGURED = True


def _vkey_to_key_value(vkey: int) -> str:
    if 0x30 <= vkey <= 0x39:
        return chr(vkey)
    if 0x41 <= vkey <= 0x5A:
        return chr(vkey).lower()
    mapping = {
        0x08: "backspace",
        0x09: "tab",
        0x0D: "enter",
        0x10: "shift",
        0x11: "ctrl",
        0x12: "alt",
        0x14: "other",
        0x1B: "other",
        0x20: "space",
        0x2E: "delete",
        0x5B: "win",
        0x5C: "win",
        0xBA: ";",
        0xBB: "=",
        0xBC: ",",
        0xBD: "-",
        0xBE: ".",
        0xBF: "/",
        0xC0: "`",
        0xDB: "[",
        0xDC: "\\",
        0xDD: "]",
        0xDE: "'",
    }
    return mapping.get(vkey, "other")
