"""Windowsセッションの数値状態だけを取得する。ユーザー情報は読まない。"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass


@dataclass(frozen=True)
class SessionState:
    locked: bool
    disconnected: bool


class _SessionPrefix(ctypes.Structure):
    _fields_ = [("session_id", ctypes.c_uint32), ("state", ctypes.c_int32), ("flags", ctypes.c_int32)]


class _SessionData(ctypes.Union):
    # WTSINFOEX_LEVEL1の後方にはLARGE_INTEGERがあり、unionは8byte境界。
    # 必要な数値プレフィックスだけを参照し、ユーザー名等にはアクセスしない。
    _fields_ = [("session", _SessionPrefix), ("_alignment", ctypes.c_uint64)]


class _SessionInfo(ctypes.Structure):
    _fields_ = [("level", ctypes.c_uint32), ("data", _SessionData)]


class WindowsSessionAPI:
    def __init__(self) -> None:
        self._wts = ctypes.WinDLL("wtsapi32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcessId.restype = ctypes.c_uint32
        kernel.ProcessIdToSessionId.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        kernel.ProcessIdToSessionId.restype = ctypes.c_int
        session = ctypes.c_uint32()
        if not kernel.ProcessIdToSessionId(kernel.GetCurrentProcessId(), ctypes.byref(session)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.session_id = session.value
        self._wts.WTSRegisterSessionNotification.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self._wts.WTSRegisterSessionNotification.restype = ctypes.c_int
        self._wts.WTSUnRegisterSessionNotification.argtypes = [ctypes.c_void_p]
        self._wts.WTSUnRegisterSessionNotification.restype = ctypes.c_int
        self._wts.WTSQuerySessionInformationW.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint32),
        ]
        self._wts.WTSQuerySessionInformationW.restype = ctypes.c_int
        self._wts.WTSFreeMemory.argtypes = [ctypes.c_void_p]
        self._wts.WTSFreeMemory.restype = None

    def register(self, hwnd: int) -> bool:
        return bool(self._wts.WTSRegisterSessionNotification(hwnd, 0))  # このセッションのみ

    def unregister(self, hwnd: int) -> None:
        self._wts.WTSUnRegisterSessionNotification(hwnd)

    def query(self) -> SessionState | None:
        buffer = ctypes.c_void_p()
        size = ctypes.c_uint32()
        try:
            if not self._wts.WTSQuerySessionInformationW(
                None, self.session_id, 25, ctypes.byref(buffer), ctypes.byref(size),
            ):
                return None
            if not buffer or size.value < ctypes.sizeof(_SessionInfo):
                return None
            info = ctypes.cast(buffer, ctypes.POINTER(_SessionInfo)).contents
            if info.level != 1 or info.data.session.flags not in (0, 1):
                return None
            return SessionState(info.data.session.flags == 0, info.data.session.state != 0)
        finally:
            if buffer:
                self._wts.WTSFreeMemory(buffer)
