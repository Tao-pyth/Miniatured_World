from __future__ import annotations

from pathlib import Path

from miniatured_world.activity import ActivityProvider, create_activity_provider
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.qt_tray import attach_tray
from miniatured_world.app.activity_startup import prepare_activity_startup


def run_qt_app(
    seed: int,
    data_root: Path | None = None,
    provider: ActivityProvider | None = None,
    *,
    activity_provider: str = "auto",
    duration_seconds: float | None = None,
    tick_interval_ms: int = 1000,
    stability_log: Path | None = None,
) -> int:
    """解決済みの保存先で起動する。Noneは設定・発見を保存しない。"""
    from PySide6.QtWidgets import QApplication
    from miniatured_world.app.qt_activity_notice import attach_activity_notice, choose_activity
    from miniatured_world.app.qt_session import create_session_monitor

    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    runtime = AppRuntime.start(seed=seed, provider=provider, data_root=data_root)
    if provider is None and not prepare_activity_startup(
        runtime, activity_provider, lambda: create_activity_provider(activity_provider), choose_activity,
    ):
        return 0
    window = build_main_window(
        runtime,
        duration_seconds=duration_seconds,
        tick_interval_ms=tick_interval_ms,
        stability_log=stability_log,
        on_stability_complete=app.quit,
        on_exit=app.quit,
    )
    if provider is None and activity_provider not in ("demo", "none") and runtime.service.settings.activity_notice == "legacy":
        attach_activity_notice(window, runtime)
    window.tray = attach_tray(app, window, runtime)
    app.aboutToQuit.connect(window.shutdown)
    app.installEventFilter(window)
    session_monitor = create_session_monitor(runtime, window.refresh)
    if session_monitor is not None:
        app.aboutToQuit.connect(session_monitor.stop)
    window.show()
    try:
        return app.exec()
    finally:
        window.shutdown()
        app.aboutToQuit.disconnect(window.shutdown)
        app.removeEventFilter(window)
        if session_monitor is not None:
            session_monitor.stop()
