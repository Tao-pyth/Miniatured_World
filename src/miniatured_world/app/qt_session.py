from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from miniatured_world.app.windows_session import WindowsSessionAPI

WM_WTSSESSION_CHANGE = 0x02B1
WM_POWERBROADCAST = 0x0218


def create_session_monitor(runtime, on_change, *, api=None):
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QWidget

    if api is None and (sys.platform != "win32" or QGuiApplication.platformName() != "windows"):
        return None

    class SessionMonitor(QWidget):
        def __init__(self):
            super().__init__(None, Qt.WindowType.Tool)
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
            self._api = api
            self._registered = False
            self._stopped = False
            self._handle = int(self.winId())
            self.retry_timer = QTimer(self)
            self.retry_timer.timeout.connect(self.synchronize)
            self.retry_timer.start(5000)
            self.synchronize()

        def _set(self, reason, suspended):
            runtime.set_system_suspended(reason, suspended)

        def synchronize(self):
            if self._stopped:
                return
            try:
                if self._api is None:
                    self._api = WindowsSessionAPI()
                if not self._registered:
                    self._registered = self._api.register(self._handle)
                state = self._api.query() if self._registered else None
            except OSError:
                state = None
            if state is None:
                self._set("session_unavailable", True)
                if not self.retry_timer.isActive():
                    self.retry_timer.start(5000)
            else:
                reasons = {"session_locked": state.locked, "session_disconnected": state.disconnected}
                # 追加を先に適用し、休止理由の切替で一瞬再開するのを防ぐ。
                for reason, suspended in reasons.items():
                    if suspended:
                        self._set(reason, True)
                for reason, suspended in reasons.items():
                    if not suspended:
                        self._set(reason, False)
                self._set("session_unavailable", False)
                self.retry_timer.stop()
            on_change(runtime.snapshot())

        def handle_message(self, message, wparam, lparam):
            if self._stopped:
                return
            if message == WM_WTSSESSION_CHANGE and self._api is not None and lparam == self._api.session_id:
                if wparam in (7, 8):
                    self._set("session_locked", wparam == 7)
                elif wparam in (2, 4):
                    self._set("session_disconnected", True)
                elif wparam in (1, 3):
                    self.synchronize()
            elif message == WM_POWERBROADCAST:
                if wparam == 4:  # PBT_APMSUSPEND
                    self._set("system_sleep", True)
                elif wparam in (7, 18):  # RESUMESUSPEND / RESUMEAUTOMATIC
                    self.synchronize()
                    self._set("system_sleep", False)
            on_change(runtime.snapshot())

        def nativeEvent(self, event_type, message):  # noqa: N802
            if event_type == b"windows_generic_MSG":
                msg = wintypes.MSG.from_address(int(message))
                self.handle_message(msg.message, msg.wParam, msg.lParam)
            return False, 0

        def stop(self):
            if self._stopped:
                return
            self._stopped = True
            self.retry_timer.stop()
            if self._registered:
                self._api.unregister(self._handle)
                self._registered = False
            self.close()
            self.deleteLater()

    return SessionMonitor()
