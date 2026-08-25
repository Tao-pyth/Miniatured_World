from __future__ import annotations

from miniatured_world.app.commands import RuntimeCommand
from miniatured_world.app.runtime import AppRuntime


def attach_tray(app, window, runtime: AppRuntime):
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMenu, QStyle, QSystemTrayIcon

    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None

    tray = QSystemTrayIcon(window)
    tray.setIcon(window.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
    tray.setToolTip("Miniatured World")

    menu = QMenu(window)

    def add_action(label: str, callback):
        action = QAction(label, menu)
        action.triggered.connect(callback)
        menu.addAction(action)
        return action

    actions = {
        "show": add_action("ウィンドウを表示", window.showNormal),
        "hide": add_action("ウィンドウを隠す", window.hide),
    }
    menu.addSeparator()
    actions["pause"] = add_action("一時停止", lambda: _handle(runtime, RuntimeCommand.PAUSE, window))
    actions["resume"] = add_action("再開", lambda: _handle(runtime, RuntimeCommand.RESUME, window))
    actions["stop_activity"] = add_action("活動取得を停止", lambda: _handle(runtime, RuntimeCommand.STOP_ACTIVITY, window))
    actions["start_activity"] = add_action("活動取得を再開", lambda: _handle(runtime, RuntimeCommand.START_ACTIVITY, window))
    actions["mute"] = add_action("ミュート", lambda: _handle(runtime, RuntimeCommand.MUTE, window))
    actions["unmute"] = add_action("ミュート解除", lambda: _handle(runtime, RuntimeCommand.UNMUTE, window))
    menu.addSeparator()
    actions["settings"] = add_action("設定", lambda: _show_tab(window, "設定"))
    actions["discovery"] = add_action("発見", lambda: _show_tab(window, "発見"))
    menu.addSeparator()
    actions["exit"] = add_action("終了", lambda: _exit(app, runtime, window))

    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: window.showNormal()
        if reason == QSystemTrayIcon.ActivationReason.Trigger
        else None
    )
    tray.show()
    tray._miniatured_world_actions = actions
    return tray


def _handle(runtime: AppRuntime, command: RuntimeCommand, window) -> None:
    runtime.handle(command)
    window.refresh(runtime.snapshot())


def _show_tab(window, label: str) -> None:
    window.showNormal()
    for index in range(window.tabs.count()):
        if window.tabs.tabText(index) == label:
            window.tabs.setCurrentIndex(index)
            break


def _exit(app, runtime: AppRuntime, window) -> None:
    runtime.handle(RuntimeCommand.EXIT)
    window.close()
    app.quit()
