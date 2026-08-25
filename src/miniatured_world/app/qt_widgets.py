from __future__ import annotations

from collections.abc import Callable

from miniatured_world.app.commands import RuntimeCommand
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.snapshot import WorldSnapshot
from miniatured_world.persistence.settings import Settings


def build_main_window(runtime: AppRuntime):
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QColor, QPainter, QPen
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QMainWindow,
        QPushButton,
        QSlider,
        QSpinBox,
        QStyle,
        QTabWidget,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )

    class _WorldPreviewWidget(QWidget):
        _colors = {
            "sand": QColor("#c9a86a"),
            "soil": QColor("#6f5a3a"),
            "seed": QColor("#83a65b"),
            "water": QColor("#4f8fb8"),
            "mineral": QColor("#8f97a3"),
            "food": QColor("#c57b57"),
        }

        def __init__(self) -> None:
            super().__init__()
            self._snapshot: WorldSnapshot | None = None
            self.setMinimumSize(520, 300)

        def set_snapshot(self, snapshot: WorldSnapshot) -> None:
            self._snapshot = snapshot
            self.update()

        def paintEvent(self, event) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = self.rect()
            painter.fillRect(rect, QColor("#172026"))

            snapshot = self._snapshot
            if snapshot is None:
                return

            sky_height = int(rect.height() * 0.52)
            painter.fillRect(0, 0, rect.width(), sky_height, QColor("#22323b"))
            painter.fillRect(0, sky_height, rect.width(), rect.height() - sky_height, QColor("#243027"))

            material_items = list(snapshot.grid_materials.items()) or list(snapshot.materials.items())
            total = max(1, sum(count for _, count in material_items))
            x = 0
            ground_top = int(rect.height() * 0.64)
            for material_id, count in material_items:
                width = max(8, int(rect.width() * count / total))
                color = self._colors.get(material_id, QColor("#7c8790"))
                painter.fillRect(x, ground_top, width, rect.height() - ground_top, color)
                x += width
            if x < rect.width():
                painter.fillRect(x, ground_top, rect.width() - x, rect.height() - ground_top, QColor("#314037"))

            painter.setPen(QPen(QColor("#7fb069"), 3))
            for index in range(snapshot.plant_count):
                plant_x = 48 + index * 34
                if plant_x >= rect.width() - 24:
                    break
                base_y = ground_top + 18
                painter.drawLine(plant_x, base_y, plant_x, base_y - 38)
                painter.drawLine(plant_x, base_y - 26, plant_x - 12, base_y - 36)
                painter.drawLine(plant_x, base_y - 22, plant_x + 12, base_y - 34)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#d6c7a1"))
            for index in range(snapshot.creature_count):
                creature_x = rect.width() - 70 - index * 34
                creature_y = ground_top + 28
                painter.drawEllipse(creature_x, creature_y, 18, 12)

            painter.setPen(QColor("#b8c2cc"))
            painter.drawText(18, 28, f"{snapshot.tendency} / {snapshot.activity_level}")

    class _InfoPill(QFrame):
        def __init__(self, title: str) -> None:
            super().__init__()
            self.setFrameShape(QFrame.Shape.StyledPanel)
            self.setObjectName("InfoPill")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(12, 8, 12, 8)
            self._title = QLabel(title)
            self._value = QLabel("-")
            self._title.setObjectName("PillTitle")
            self._value.setObjectName("PillValue")
            layout.addWidget(self._title)
            layout.addWidget(self._value)

        def set_value(self, value: object) -> None:
            self._value.setText(str(value))

    class _WorldTab(QWidget):
        def __init__(self, runtime: AppRuntime) -> None:
            super().__init__()
            self._runtime = runtime
            self.preview = _WorldPreviewWidget()
            self.tendency = _InfoPill("Tendency")
            self.traits = _InfoPill("Traits")
            self.activity = _InfoPill("Activity")
            self.world_time = _InfoPill("World Time")
            self.materials = _InfoPill("Materials")
            self.events = _InfoPill("Events")
            self.discoveries = _InfoPill("Discoveries")
            self.status = _InfoPill("Status")

            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)
            layout.addWidget(self.preview)

            grid = QGridLayout()
            for index, pill in enumerate(
                (
                    self.tendency,
                    self.traits,
                    self.activity,
                    self.world_time,
                    self.materials,
                    self.events,
                    self.discoveries,
                    self.status,
                )
            ):
                grid.addWidget(pill, index // 4, index % 4)
            layout.addLayout(grid)

            controls = QHBoxLayout()
            controls.setSpacing(8)
            self.pause_button = _tool_button("Pause", QStyle.StandardPixmap.SP_MediaPause, RuntimeCommand.TOGGLE_PAUSE)
            self.activity_button = _tool_button("Activity", QStyle.StandardPixmap.SP_DialogApplyButton, RuntimeCommand.STOP_ACTIVITY)
            self.visibility_button = _tool_button("Hide", QStyle.StandardPixmap.SP_TitleBarShadeButton, RuntimeCommand.HIDE_WORLD)
            self.mute_button = _tool_button("Mute", QStyle.StandardPixmap.SP_MediaVolumeMuted, RuntimeCommand.TOGGLE_MUTE)
            self.exit_button = _tool_button("Exit", QStyle.StandardPixmap.SP_DialogCloseButton, RuntimeCommand.EXIT)
            for button in (
                self.pause_button,
                self.activity_button,
                self.visibility_button,
                self.mute_button,
                self.exit_button,
            ):
                button.clicked.connect(lambda checked=False, b=button: self._handle_button(b))
                controls.addWidget(button)
            controls.addStretch(1)
            layout.addLayout(controls)

        def refresh(self, snapshot: WorldSnapshot) -> None:
            self.preview.setVisible(snapshot.world_visible)
            self.preview.set_snapshot(snapshot)
            self.tendency.set_value(snapshot.tendency)
            self.traits.set_value(", ".join(snapshot.traits) or "-")
            self.activity.set_value(snapshot.activity_level)
            self.world_time.set_value(f"{snapshot.world_time:.1f}")
            self.materials.set_value(sum(snapshot.materials.values()))
            self.events.set_value(len(snapshot.events))
            self.discoveries.set_value(len(snapshot.discoveries))
            self.status.set_value(_status_text(snapshot))
            self.pause_button.setText("Resume" if snapshot.paused else "Pause")
            self.activity_button.setText("Start Activity" if not snapshot.activity_collection_enabled else "Stop Activity")
            self.activity_button.setProperty(
                "runtime_command",
                RuntimeCommand.START_ACTIVITY if not snapshot.activity_collection_enabled else RuntimeCommand.STOP_ACTIVITY,
            )
            self.visibility_button.setText("Show" if not snapshot.world_visible else "Hide")
            self.visibility_button.setProperty(
                "runtime_command",
                RuntimeCommand.SHOW_WORLD if not snapshot.world_visible else RuntimeCommand.HIDE_WORLD,
            )
            self.mute_button.setText("Unmute" if snapshot.muted else "Mute")

        def _handle_button(self, button: QToolButton) -> None:
            command = button.property("runtime_command")
            self._runtime.handle(command)

    class _SettingsTab(QWidget):
        def __init__(self, settings: Settings, runtime: AppRuntime) -> None:
            super().__init__()
            self._runtime = runtime
            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            tabs = QTabWidget()
            tabs.addTab(_general_settings(settings), "General")
            tabs.addTab(_display_settings(settings), "Display")
            tabs.addTab(_activity_settings(settings, runtime), "Activity")
            tabs.addTab(_sound_settings(settings, runtime), "Sound")
            tabs.addTab(_notification_settings(settings), "Notifications")
            tabs.addTab(_privacy_settings(settings), "Privacy")
            tabs.addTab(_performance_settings(settings), "Performance")
            tabs.addTab(_data_settings(settings), "Data")
            layout.addWidget(tabs)

    class _DiscoveryTab(QWidget):
        def __init__(self) -> None:
            super().__init__()
            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            self.summary = QLabel("0 discoveries")
            self.list_widget = QListWidget()
            self.list_widget.setMinimumHeight(320)
            layout.addWidget(self.summary)
            layout.addWidget(self.list_widget)

        def refresh(self, snapshot: WorldSnapshot) -> None:
            self.list_widget.clear()
            if not snapshot.discoveries:
                self.list_widget.addItem("No discoveries")
            else:
                for discovery in snapshot.discoveries:
                    self.list_widget.addItem(discovery)
            self.summary.setText(f"{len(snapshot.discoveries)} discoveries")

    class _MiniaturedWorldMainWindow(QMainWindow):
        def __init__(self, runtime: AppRuntime) -> None:
            super().__init__()
            self.runtime = runtime
            self.setWindowTitle("Miniatured World")
            self.setMinimumSize(900, 620)

            self.tabs = QTabWidget()
            self.world_tab = _WorldTab(runtime)
            self.settings_tab = _SettingsTab(runtime.service.settings, runtime)
            self.discovery_tab = _DiscoveryTab()
            self.tabs.addTab(self.world_tab, "World")
            self.tabs.addTab(self.settings_tab, "Settings")
            self.tabs.addTab(self.discovery_tab, "Discovery")
            self.setCentralWidget(self.tabs)
            self.setStyleSheet(_style_sheet())

            self.timer = QTimer(self)
            self.timer.timeout.connect(self.advance)
            self.timer.start(1000)
            self.refresh(runtime.snapshot())

        def advance(self) -> None:
            snapshot = self.runtime.tick()
            self.refresh(snapshot)
            if not snapshot.running:
                self.close()

        def refresh(self, snapshot: WorldSnapshot) -> None:
            self.world_tab.refresh(snapshot)
            self.discovery_tab.refresh(snapshot)

    def _tool_button(label: str, icon: QStyle.StandardPixmap, command: RuntimeCommand) -> QToolButton:
        button = QToolButton()
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setText(label)
        button.setIcon(button.style().standardIcon(icon))
        button.setToolTip(label)
        button.setMinimumHeight(34)
        button.setProperty("runtime_command", command)
        return button

    def _group(title: str, rows: list[tuple[str, object]]) -> QWidget:
        box = QGroupBox(title)
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        for label, widget in rows:
            form.addRow(label, widget)
        return box

    def _check(value: bool, enabled: bool = True, on_change: Callable[[bool], None] | None = None) -> QCheckBox:
        checkbox = QCheckBox()
        checkbox.setChecked(value)
        checkbox.setEnabled(enabled)
        if on_change:
            checkbox.toggled.connect(on_change)
        return checkbox

    def _spin(value: int, minimum: int, maximum: int, step: int = 1) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setValue(value)
        return spin

    def _slider(value: float, minimum: int = 0, maximum: int = 100) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(int(value * 100))
        return slider

    def _combo(value: str, options: tuple[str, ...]) -> QComboBox:
        combo = QComboBox()
        combo.addItems(options)
        combo.setCurrentText(value)
        return combo

    def _general_settings(settings: Settings) -> QWidget:
        return _group(
            "General",
            [
                ("Launch on login", _check(settings.general.launch_on_login)),
                ("Minimize to tray", _check(settings.general.minimize_to_tray)),
                ("Show world on start", _check(settings.general.show_world_on_start)),
                ("Restore window position", _check(settings.general.restore_window_position)),
                ("Confirm on exit", _check(settings.general.confirm_on_exit)),
                ("Language", _combo(settings.general.language, ("ja", "en"))),
            ],
        )

    def _display_settings(settings: Settings) -> QWidget:
        return _group(
            "Display",
            [
                ("View mode", _combo(settings.display.view_mode, ("window", "desktop", "preview"))),
                ("Always on top", _check(settings.display.always_on_top)),
                ("Click through", _check(settings.display.click_through)),
                ("Opacity", _slider(settings.display.opacity)),
                ("FPS limit", _spin(settings.display.fps_limit, 15, 120, 5)),
                ("Quality", _combo(settings.display.quality, ("automatic", "low", "medium", "high"))),
            ],
        )

    def _activity_settings(settings: Settings, runtime: AppRuntime) -> QWidget:
        return _group(
            "Activity",
            [
                ("Enabled", _check(settings.activity.enabled, on_change=runtime.set_activity_collection)),
                ("Keyboard", _check(settings.activity.keyboard_enabled)),
                ("Mouse", _check(settings.activity.mouse_enabled)),
                ("Click", _check(settings.activity.click_enabled)),
                ("Scroll", _check(settings.activity.scroll_enabled)),
                ("Frame window ms", _spin(settings.activity.frame_window_ms, 100, 5000, 100)),
                ("Reflection", _slider(settings.activity.reflection_strength)),
            ],
        )

    def _sound_settings(settings: Settings, runtime: AppRuntime) -> QWidget:
        return _group(
            "Sound",
            [
                ("Enabled", _check(settings.sound.enabled, on_change=lambda enabled: runtime.unmute() if enabled else runtime.mute())),
                ("Master volume", _slider(settings.sound.master_volume)),
                ("Ambience", _slider(settings.sound.ambience_volume)),
                ("Events", _slider(settings.sound.event_volume)),
            ],
        )

    def _notification_settings(settings: Settings) -> QWidget:
        return _group(
            "Notifications",
            [
                ("Milestone", _check(settings.notifications.milestone_enabled)),
                ("Rare phenomenon", _check(settings.notifications.rare_phenomenon_enabled)),
                ("Discovery", _check(settings.notifications.discovery_enabled)),
                ("Tray", _check(settings.notifications.tray_enabled)),
                ("Duration ms", _spin(settings.notifications.duration_ms, 1000, 12000, 500)),
            ],
        )

    def _privacy_settings(settings: Settings) -> QWidget:
        return _group(
            "Privacy",
            [
                ("Store raw input", _check(settings.privacy.store_raw_input, enabled=False)),
                ("Store window titles", _check(settings.privacy.store_window_titles, enabled=False)),
                ("Store clipboard", _check(settings.privacy.store_clipboard, enabled=False)),
                ("Store screen capture", _check(settings.privacy.store_screen_capture, enabled=False)),
                ("Upload activity", _check(settings.privacy.external_activity_upload, enabled=False)),
            ],
        )

    def _performance_settings(settings: Settings) -> QWidget:
        return _group(
            "Performance",
            [
                ("Max particles", _spin(settings.performance.max_particles, 100, 20000, 100)),
                ("Max creatures", _spin(settings.performance.max_creatures, 1, 500, 1)),
                ("Simulation quality", _combo(settings.performance.simulation_quality, ("automatic", "low", "medium", "high"))),
                ("CPU limit", _spin(settings.performance.cpu_limit_percent, 1, 100, 1)),
                ("Battery saver", _check(settings.performance.battery_saver)),
            ],
        )

    def _data_settings(settings: Settings) -> QWidget:
        return _group(
            "Data",
            [
                ("Save discovery", _check(settings.data.save_discovery)),
                ("Save settings", _check(settings.data.save_settings)),
                ("Schema version", _spin(settings.data.schema_version, 1, 99, 1)),
            ],
        )

    def _status_text(snapshot: WorldSnapshot) -> str:
        if not snapshot.running:
            return "stopped"
        if snapshot.paused:
            return "paused"
        if not snapshot.activity_collection_enabled:
            return "activity off"
        return "running"

    def _style_sheet() -> str:
        return """
        QMainWindow, QWidget {
          background: #f6f7f4;
          color: #1f2933;
          font-size: 13px;
        }
        QTabWidget::pane {
          border: 1px solid #cfd6dc;
          background: #ffffff;
        }
        QTabBar::tab {
          min-width: 104px;
          min-height: 30px;
          padding: 6px 12px;
          background: #e8ece7;
          border: 1px solid #cfd6dc;
        }
        QTabBar::tab:selected {
          background: #ffffff;
          border-bottom-color: #ffffff;
        }
        QFrame#InfoPill, QGroupBox {
          background: #ffffff;
          border: 1px solid #d7dde2;
          border-radius: 6px;
        }
        QLabel#PillTitle {
          color: #5c6873;
          font-size: 11px;
        }
        QLabel#PillValue {
          color: #172026;
          font-size: 15px;
          font-weight: 600;
        }
        QToolButton, QPushButton {
          background: #ffffff;
          border: 1px solid #c7d0d8;
          border-radius: 5px;
          padding: 6px 10px;
        }
        QToolButton:hover, QPushButton:hover {
          background: #eef4f7;
        }
        QGroupBox {
          margin-top: 12px;
          padding: 16px 10px 10px 10px;
          font-weight: 600;
        }
        QListWidget {
          background: #ffffff;
          border: 1px solid #d7dde2;
          border-radius: 6px;
        }
        """

    return _MiniaturedWorldMainWindow(runtime)
