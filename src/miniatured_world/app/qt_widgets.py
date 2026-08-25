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
            painter.drawText(18, 28, f"傾向: {_display_value(snapshot.tendency)} / 活動: {_display_value(snapshot.activity_level)}")

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
            self.tendency = _InfoPill("傾向")
            self.traits = _InfoPill("特性")
            self.activity = _InfoPill("活動")
            self.world_time = _InfoPill("世界時間")
            self.materials = _InfoPill("素材")
            self.events = _InfoPill("イベント")
            self.discoveries = _InfoPill("発見")
            self.status = _InfoPill("状態")

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
            self.pause_button = _tool_button("一時停止", QStyle.StandardPixmap.SP_MediaPause, RuntimeCommand.TOGGLE_PAUSE)
            self.activity_button = _tool_button("活動停止", QStyle.StandardPixmap.SP_DialogApplyButton, RuntimeCommand.STOP_ACTIVITY)
            self.visibility_button = _tool_button("非表示", QStyle.StandardPixmap.SP_TitleBarShadeButton, RuntimeCommand.HIDE_WORLD)
            self.mute_button = _tool_button("ミュート", QStyle.StandardPixmap.SP_MediaVolumeMuted, RuntimeCommand.TOGGLE_MUTE)
            self.exit_button = _tool_button("終了", QStyle.StandardPixmap.SP_DialogCloseButton, RuntimeCommand.EXIT)
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
            self.tendency.set_value(_display_value(snapshot.tendency))
            self.traits.set_value(", ".join(_display_value(trait) for trait in snapshot.traits) or "-")
            self.activity.set_value(_display_value(snapshot.activity_level))
            self.world_time.set_value(f"{snapshot.world_time:.1f}")
            self.materials.set_value(sum(snapshot.materials.values()))
            self.events.set_value(len(snapshot.events))
            self.discoveries.set_value(len(snapshot.discoveries))
            self.status.set_value(_status_text(snapshot))
            self.pause_button.setText("再開" if snapshot.paused else "一時停止")
            self.activity_button.setText("活動再開" if not snapshot.activity_collection_enabled else "活動停止")
            self.activity_button.setProperty(
                "runtime_command",
                RuntimeCommand.START_ACTIVITY if not snapshot.activity_collection_enabled else RuntimeCommand.STOP_ACTIVITY,
            )
            self.visibility_button.setText("表示" if not snapshot.world_visible else "非表示")
            self.visibility_button.setProperty(
                "runtime_command",
                RuntimeCommand.SHOW_WORLD if not snapshot.world_visible else RuntimeCommand.HIDE_WORLD,
            )
            self.mute_button.setText("ミュート解除" if snapshot.muted else "ミュート")

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
            tabs.addTab(_general_settings(settings, runtime), "一般")
            tabs.addTab(_display_settings(settings, runtime), "表示")
            tabs.addTab(_activity_settings(settings, runtime), "活動")
            tabs.addTab(_sound_settings(settings, runtime), "サウンド")
            tabs.addTab(_notification_settings(settings, runtime), "通知")
            tabs.addTab(_privacy_settings(settings), "プライバシー")
            tabs.addTab(_performance_settings(settings, runtime), "性能")
            tabs.addTab(_data_settings(settings, runtime), "データ")
            layout.addWidget(tabs)

    class _DiscoveryTab(QWidget):
        def __init__(self) -> None:
            super().__init__()
            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            self.summary = QLabel("0件の発見")
            self.list_widget = QListWidget()
            self.list_widget.setMinimumHeight(320)
            layout.addWidget(self.summary)
            layout.addWidget(self.list_widget)

        def refresh(self, snapshot: WorldSnapshot) -> None:
            self.list_widget.clear()
            if not snapshot.discoveries:
                self.list_widget.addItem("発見なし")
            else:
                for discovery in snapshot.discoveries:
                    self.list_widget.addItem(_display_value(discovery))
            self.summary.setText(f"{len(snapshot.discoveries)}件の発見")

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
            self.tabs.addTab(self.world_tab, "ワールド")
            self.tabs.addTab(self.settings_tab, "設定")
            self.tabs.addTab(self.discovery_tab, "発見")
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
            if hasattr(widget, "setObjectName"):
                widget.setObjectName(_object_name(title, label))
            form.addRow(label, widget)
        return box

    def _object_name(title: str, label: str) -> str:
        terms = {
            "一般": "general",
            "表示": "display",
            "活動": "activity",
            "サウンド": "sound",
            "通知": "notifications",
            "プライバシー": "privacy",
            "性能": "performance",
            "データ": "data",
            "ログイン時に起動": "launch_on_login",
            "トレイへ最小化": "minimize_to_tray",
            "起動時にワールド表示": "show_world_on_start",
            "表示位置を復元": "restore_window_position",
            "終了確認": "confirm_on_exit",
            "言語": "language",
            "表示モード": "view_mode",
            "常に最前面": "always_on_top",
            "クリック透過": "click_through",
            "不透明度": "opacity",
            "FPS上限": "fps_limit",
            "品質": "quality",
            "有効": "enabled",
            "キーボード": "keyboard",
            "マウス": "mouse",
            "クリック": "click",
            "スクロール": "scroll",
            "集約間隔ms": "frame_window_ms",
            "反映量": "reflection",
            "マスター音量": "master_volume",
            "環境音": "ambience",
            "イベント音": "events",
            "マイルストーン": "milestone",
            "希少現象": "rare_phenomenon",
            "発見": "discovery",
            "トレイ": "tray",
            "表示時間ms": "duration_ms",
            "Raw Inputを保存": "store_raw_input",
            "Window Titleを保存": "store_window_titles",
            "クリップボードを保存": "store_clipboard",
            "画面キャプチャを保存": "store_screen_capture",
            "Activityを送信": "upload_activity",
            "最大粒子数": "max_particles",
            "最大生物数": "max_creatures",
            "Simulation品質": "simulation_quality",
            "CPU上限": "cpu_limit",
            "バッテリー節約": "battery_saver",
            "発見を保存": "save_discovery",
            "設定を保存": "save_settings",
            "スキーマバージョン": "schema_version",
        }
        title = terms.get(title, title)
        label = terms.get(label, label)
        normalized = f"{title}_{label}".lower().replace(" ", "_").replace("/", "_")
        return "".join(character for character in normalized if character.isalnum() or character == "_")

    def _setting(runtime: AppRuntime, section: str, field_name: str, transform: Callable[[object], object] | None = None):
        def update(value: object) -> None:
            runtime.update_setting(section, field_name, transform(value) if transform else value)

        return update

    def _check(value: bool, enabled: bool = True, on_change: Callable[[bool], None] | None = None) -> QCheckBox:
        checkbox = QCheckBox()
        checkbox.setChecked(value)
        checkbox.setEnabled(enabled)
        if on_change:
            checkbox.toggled.connect(on_change)
        return checkbox

    def _spin(
        value: int,
        minimum: int,
        maximum: int,
        step: int = 1,
        on_change: Callable[[int], None] | None = None,
    ) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setValue(value)
        if on_change:
            spin.valueChanged.connect(on_change)
        return spin

    def _slider(
        value: float,
        minimum: int = 0,
        maximum: int = 100,
        on_change: Callable[[int], None] | None = None,
    ) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(int(value * 100))
        if on_change:
            slider.valueChanged.connect(on_change)
        return slider

    def _combo(value: str, options: tuple[str, ...], on_change: Callable[[str], None] | None = None) -> QComboBox:
        combo = QComboBox()
        combo.addItems(options)
        combo.setCurrentText(value)
        if on_change:
            combo.currentTextChanged.connect(on_change)
        return combo

    def _general_settings(settings: Settings, runtime: AppRuntime) -> QWidget:
        return _group(
            "一般",
            [
                ("ログイン時に起動", _check(settings.general.launch_on_login, on_change=_setting(runtime, "general", "launch_on_login"))),
                ("トレイへ最小化", _check(settings.general.minimize_to_tray, on_change=_setting(runtime, "general", "minimize_to_tray"))),
                ("起動時にワールド表示", _check(settings.general.show_world_on_start, on_change=_setting(runtime, "general", "show_world_on_start"))),
                ("表示位置を復元", _check(settings.general.restore_window_position, on_change=_setting(runtime, "general", "restore_window_position"))),
                ("終了確認", _check(settings.general.confirm_on_exit, on_change=_setting(runtime, "general", "confirm_on_exit"))),
                ("言語", _combo(settings.general.language, ("ja", "en"), on_change=_setting(runtime, "general", "language"))),
            ],
        )

    def _display_settings(settings: Settings, runtime: AppRuntime) -> QWidget:
        return _group(
            "表示",
            [
                ("表示モード", _combo(settings.display.view_mode, ("window", "desktop", "preview"), on_change=_setting(runtime, "display", "view_mode"))),
                ("常に最前面", _check(settings.display.always_on_top, on_change=_setting(runtime, "display", "always_on_top"))),
                ("クリック透過", _check(settings.display.click_through, on_change=_setting(runtime, "display", "click_through"))),
                ("不透明度", _slider(settings.display.opacity, on_change=_setting(runtime, "display", "opacity", lambda value: int(value) / 100.0))),
                ("FPS上限", _spin(settings.display.fps_limit, 15, 120, 5, on_change=_setting(runtime, "display", "fps_limit"))),
                ("品質", _combo(settings.display.quality, ("automatic", "low", "medium", "high"), on_change=_setting(runtime, "display", "quality"))),
            ],
        )

    def _activity_settings(settings: Settings, runtime: AppRuntime) -> QWidget:
        return _group(
            "活動",
            [
                ("有効", _check(settings.activity.enabled, on_change=runtime.set_activity_collection)),
                ("キーボード", _check(settings.activity.keyboard_enabled, on_change=_setting(runtime, "activity", "keyboard_enabled"))),
                ("マウス", _check(settings.activity.mouse_enabled, on_change=_setting(runtime, "activity", "mouse_enabled"))),
                ("クリック", _check(settings.activity.click_enabled, on_change=_setting(runtime, "activity", "click_enabled"))),
                ("スクロール", _check(settings.activity.scroll_enabled, on_change=_setting(runtime, "activity", "scroll_enabled"))),
                ("集約間隔ms", _spin(settings.activity.frame_window_ms, 100, 5000, 100, on_change=_setting(runtime, "activity", "frame_window_ms"))),
                ("反映量", _slider(settings.activity.reflection_strength, on_change=_setting(runtime, "activity", "reflection_strength", lambda value: int(value) / 100.0))),
            ],
        )

    def _sound_settings(settings: Settings, runtime: AppRuntime) -> QWidget:
        return _group(
            "サウンド",
            [
                ("有効", _check(settings.sound.enabled, on_change=lambda enabled: runtime.unmute() if enabled else runtime.mute())),
                ("マスター音量", _slider(settings.sound.master_volume, on_change=_setting(runtime, "sound", "master_volume", lambda value: int(value) / 100.0))),
                ("環境音", _slider(settings.sound.ambience_volume, on_change=_setting(runtime, "sound", "ambience_volume", lambda value: int(value) / 100.0))),
                ("イベント音", _slider(settings.sound.event_volume, on_change=_setting(runtime, "sound", "event_volume", lambda value: int(value) / 100.0))),
            ],
        )

    def _notification_settings(settings: Settings, runtime: AppRuntime) -> QWidget:
        return _group(
            "通知",
            [
                ("マイルストーン", _check(settings.notifications.milestone_enabled, on_change=_setting(runtime, "notifications", "milestone_enabled"))),
                ("希少現象", _check(settings.notifications.rare_phenomenon_enabled, on_change=_setting(runtime, "notifications", "rare_phenomenon_enabled"))),
                ("発見", _check(settings.notifications.discovery_enabled, on_change=_setting(runtime, "notifications", "discovery_enabled"))),
                ("トレイ", _check(settings.notifications.tray_enabled, on_change=_setting(runtime, "notifications", "tray_enabled"))),
                ("表示時間ms", _spin(settings.notifications.duration_ms, 1000, 12000, 500, on_change=_setting(runtime, "notifications", "duration_ms"))),
            ],
        )

    def _privacy_settings(settings: Settings) -> QWidget:
        return _group(
            "プライバシー",
            [
                ("Raw Inputを保存", _check(settings.privacy.store_raw_input, enabled=False)),
                ("Window Titleを保存", _check(settings.privacy.store_window_titles, enabled=False)),
                ("クリップボードを保存", _check(settings.privacy.store_clipboard, enabled=False)),
                ("画面キャプチャを保存", _check(settings.privacy.store_screen_capture, enabled=False)),
                ("Activityを送信", _check(settings.privacy.external_activity_upload, enabled=False)),
            ],
        )

    def _performance_settings(settings: Settings, runtime: AppRuntime) -> QWidget:
        return _group(
            "性能",
            [
                ("最大粒子数", _spin(settings.performance.max_particles, 100, 20000, 100, on_change=_setting(runtime, "performance", "max_particles"))),
                ("最大生物数", _spin(settings.performance.max_creatures, 1, 500, 1, on_change=_setting(runtime, "performance", "max_creatures"))),
                ("Simulation品質", _combo(settings.performance.simulation_quality, ("automatic", "low", "medium", "high"), on_change=_setting(runtime, "performance", "simulation_quality"))),
                ("CPU上限", _spin(settings.performance.cpu_limit_percent, 1, 100, 1, on_change=_setting(runtime, "performance", "cpu_limit_percent"))),
                ("バッテリー節約", _check(settings.performance.battery_saver, on_change=_setting(runtime, "performance", "battery_saver"))),
            ],
        )

    def _data_settings(settings: Settings, runtime: AppRuntime) -> QWidget:
        return _group(
            "データ",
            [
                ("発見を保存", _check(settings.data.save_discovery, on_change=_setting(runtime, "data", "save_discovery"))),
                ("設定を保存", _check(settings.data.save_settings, on_change=_setting(runtime, "data", "save_settings"))),
                ("スキーマバージョン", _spin(settings.data.schema_version, 1, 99, 1)),
            ],
        )

    def _status_text(snapshot: WorldSnapshot) -> str:
        if not snapshot.running:
            return "停止"
        if snapshot.paused:
            return "一時停止中"
        if not snapshot.activity_collection_enabled:
            return "活動停止中"
        return "稼働中"

    def _display_value(value: str) -> str:
        labels = {
            "forest": "森",
            "wetland": "湿地",
            "desert": "砂漠",
            "crystal": "結晶",
            "windy": "風が強い",
            "mineral_rich": "鉱物が豊富",
            "humid": "湿潤",
            "quiet_growth": "静かな成長",
            "quiet": "静か",
            "calm": "穏やか",
            "active": "活発",
            "intense": "高密度",
            "plant:sprout": "植物: 芽",
            "creature:mote": "生物: モート",
            "first_rain": "初めての雨",
            "quiet_night": "静かな夜",
            "rainbow": "虹",
        }
        return labels.get(value, value)

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
