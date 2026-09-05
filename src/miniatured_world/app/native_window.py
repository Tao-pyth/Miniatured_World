from __future__ import annotations

import ctypes
import os


GWL_EXSTYLE = -20
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020


def set_windows_click_through(hwnd: int, enabled: bool) -> bool:
    if os.name != "nt" or hwnd == 0:
        return False

    user32 = ctypes.windll.user32
    _configure_user32(user32)

    ctypes.windll.kernel32.SetLastError(0)
    current_style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    if current_style == 0 and ctypes.windll.kernel32.GetLastError() != 0:
        return False

    if enabled:
        next_style = current_style | WS_EX_LAYERED | WS_EX_TRANSPARENT
    else:
        next_style = current_style & ~WS_EX_TRANSPARENT

    if next_style == current_style:
        return True

    result = user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, next_style)
    if result == 0 and ctypes.windll.kernel32.GetLastError() != 0:
        return False

    user32.SetWindowPos(
        hwnd,
        0,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
    )
    return True


def _configure_user32(user32) -> None:
    get_window_long_ptr = user32.GetWindowLongPtrW
    set_window_long_ptr = user32.SetWindowLongPtrW
    get_window_long_ptr.argtypes = [ctypes.c_void_p, ctypes.c_int]
    get_window_long_ptr.restype = ctypes.c_ssize_t
    set_window_long_ptr.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    set_window_long_ptr.restype = ctypes.c_ssize_t
    user32.SetWindowPos.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    user32.SetWindowPos.restype = ctypes.c_int
