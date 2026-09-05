from __future__ import annotations

import math
from importlib import resources
from collections.abc import Callable
from pathlib import Path

from miniatured_world.app.commands import RuntimeCommand
from miniatured_world.app.lab import LabAnimation
from miniatured_world.app.native_window import set_windows_click_through
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.snapshot import WorldSnapshot
from miniatured_world.app.stability import StabilityLogWriter
from miniatured_world.persistence.settings import Settings


def build_main_window(
    runtime: AppRuntime,
    *,
    duration_seconds: float | None = None,
    tick_interval_ms: int = 1000,
    stability_log: Path | None = None,
    on_stability_complete: Callable[[], None] | None = None,
):
    from PySide6.QtCore import QElapsedTimer, QRect, Qt, QTimer
    from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
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
            self._background = _load_lab_background()
            self._character_sprites = _load_character_sprites()
            self._cauldron_sprites = _load_cauldron_sprites()
            self.animation = LabAnimation()
            self._animation_clock = QElapsedTimer()
            self.animation_timer = QTimer(self)
            self.animation_timer.timeout.connect(self._animate)
            self.setMinimumSize(520, 300)

        def set_snapshot(self, snapshot: WorldSnapshot) -> None:
            self._snapshot = snapshot
            self.animation.observe(snapshot)
            self._sync_animation_timer()
            self.update()

        def _sync_animation_timer(self) -> None:
            snapshot = self._snapshot
            active = self.isVisible() and snapshot is not None and snapshot.running and not snapshot.paused and snapshot.world_visible
            if active:
                fps = max(1, min(30, runtime.service.settings.display.fps_limit))
                self.animation_timer.setInterval(math.ceil(1000 / fps))
                if not self.animation_timer.isActive():
                    self._animation_clock.start()
                    self.animation_timer.start()
            else:
                self.animation_timer.stop()

        def _animate(self) -> None:
            self.animation.advance(self._animation_clock.restart())
            self.update()

        def showEvent(self, event) -> None:  # noqa: N802
            super().showEvent(event)
            self._sync_animation_timer()

        def hideEvent(self, event) -> None:  # noqa: N802
            self.animation_timer.stop()
            super().hideEvent(event)

        def paintEvent(self, event) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#29282d"))

            snapshot = self._snapshot
            if snapshot is None:
                return

            # Background and sprites share one stage, including letterboxing on resize.
            scale = min(self.width() / 1280, self.height() / 853)
            painter.translate((self.width() - 1280 * scale) / 2, (self.height() - 853 * scale) / 2)
            painter.scale(scale, scale)
            rect = QRect(0, 0, 1280, 853)
            painter.setClipRect(rect)
            _draw_lab_background(painter, rect, self._background)
            scene = self.animation.scene
            if scene is None:
                return
            _draw_cauldron(painter, rect, scene.cauldron_state, self._cauldron_sprites, self.animation.frame_index)
            _draw_material_effects(painter, rect, snapshot, scene.effects, self.animation.elapsed_ms)
            _draw_alchemist(painter, rect, scene.character_state, self._character_sprites, self.animation.elapsed_ms)

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
            self.tendency = _InfoPill("ラボ傾向")
            self.traits = _InfoPill("特性")
            self.activity = _InfoPill("活動")
            self.world_time = _InfoPill("実験時間")
            self.materials = _InfoPill("素材")
            self.events = _InfoPill("イベント")
            self.discoveries = _InfoPill("発見")
            self.status = _InfoPill("ラボ状態")
            self.provider = _InfoPill("活動取得")

            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)
            layout.addWidget(self.preview, 1)

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
                    self.provider,
                )
            ):
                grid.addWidget(pill, index // 4, index % 4)
            layout.addLayout(grid)

            controls = QHBoxLayout()
            controls.setSpacing(8)
            self.pause_button = _tool_button("一時停止", QStyle.StandardPixmap.SP_MediaPause, RuntimeCommand.TOGGLE_PAUSE)
            self.activity_button = _tool_button("活動停止", QStyle.StandardPixmap.SP_DialogApplyButton, RuntimeCommand.STOP_ACTIVITY)
            self.visibility_button = _tool_button("ラボ非表示", QStyle.StandardPixmap.SP_TitleBarShadeButton, RuntimeCommand.HIDE_WORLD)
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
            self.provider.set_value(_provider_status_text(snapshot))
            self.pause_button.setText("再開" if snapshot.paused else "一時停止")
            self.activity_button.setText("活動再開" if not snapshot.activity_collection_enabled else "活動停止")
            self.activity_button.setProperty(
                "runtime_command",
                RuntimeCommand.START_ACTIVITY if not snapshot.activity_collection_enabled else RuntimeCommand.STOP_ACTIVITY,
            )
            self.visibility_button.setText("ラボ表示" if not snapshot.world_visible else "ラボ非表示")
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
            self._tick_interval_ms = tick_interval_ms
            self._stability_frame = 0
            self._stability_completed = False
            self._stability_frame_limit = (
                None
                if duration_seconds is None
                else max(1, math.ceil(duration_seconds * 1000 / self._tick_interval_ms))
            )
            self._stability_logger = (
                None
                if stability_log is None
                else StabilityLogWriter(
                    log_path=stability_log,
                    duration_seconds=duration_seconds
                    if duration_seconds is not None
                    else self._tick_interval_ms / 1000,
                    tick_interval_ms=self._tick_interval_ms,
                    realtime=True,
                )
            )
            self._on_stability_complete = on_stability_complete
            self._display_signature: tuple[str, bool, bool, float] | None = None
            self.setWindowTitle("小さなラボラトリー")
            self.setMinimumSize(900, 620)

            self.tabs = QTabWidget()
            self.world_tab = _WorldTab(runtime)
            self.settings_tab = _SettingsTab(runtime.service.settings, runtime)
            self.discovery_tab = _DiscoveryTab()
            self.tabs.addTab(self.world_tab, "ラボ")
            self.tabs.addTab(self.settings_tab, "設定")
            self.tabs.addTab(self.discovery_tab, "発見")
            self.setCentralWidget(self.tabs)
            self.setStyleSheet(_style_sheet())
            _apply_display_settings(self)

            self.timer = QTimer(self)
            self.timer.timeout.connect(self.advance)
            self.timer.start(self._tick_interval_ms)
            snapshot = runtime.snapshot()
            self.refresh(snapshot)
            if self._stability_logger is not None:
                self._stability_logger.start(snapshot)

        def advance(self) -> None:
            try:
                snapshot = self.runtime.tick(elapsed_ms=self._tick_interval_ms)
                self._stability_frame += 1
                self.refresh(snapshot)
                if self._stability_logger is not None:
                    self._stability_logger.tick(self._stability_frame, snapshot, self.runtime.service.summary_text())
                if self._stability_frame_limit is not None and self._stability_frame >= self._stability_frame_limit:
                    self._complete_stability_run(snapshot)
                    return
                if not snapshot.running:
                    self._close_stability_log(cancelled=False)
                    self.close()
            except BaseException as error:
                if self._stability_logger is not None:
                    self._stability_logger.error(error)
                    self._stability_logger.close()
                raise

        def refresh(self, snapshot: WorldSnapshot) -> None:
            _apply_display_settings(self)
            self.world_tab.refresh(snapshot)
            self.discovery_tab.refresh(snapshot)

        def closeEvent(self, event) -> None:  # noqa: N802
            self.timer.stop()
            self.world_tab.preview.animation_timer.stop()
            self._close_stability_log(cancelled=True)
            super().closeEvent(event)

        def _complete_stability_run(self, snapshot: WorldSnapshot) -> None:
            if self._stability_completed:
                return
            self._stability_completed = True
            self.runtime.stop()
            if self._stability_logger is not None:
                self._stability_logger.completed(
                    self._stability_frame,
                    snapshot,
                    self.runtime.service.summary_text(),
                )
                self._stability_logger.close()
            if self._on_stability_complete is not None:
                self._on_stability_complete()
            else:
                self.close()

        def _close_stability_log(self, *, cancelled: bool) -> None:
            if self._stability_logger is None or self._stability_logger.closed or self._stability_completed:
                return
            if cancelled:
                self._stability_logger.cancelled(
                    self._stability_frame,
                    self.runtime.snapshot(),
                    self.runtime.service.summary_text(),
                )
            self._stability_logger.close()

    def _tool_button(label: str, icon: QStyle.StandardPixmap, command: RuntimeCommand) -> QToolButton:
        button = QToolButton()
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setText(label)
        button.setIcon(button.style().standardIcon(icon))
        button.setToolTip(label)
        button.setMinimumHeight(34)
        button.setProperty("runtime_command", command)
        return button

    def _load_lab_background() -> QPixmap:
        try:
            data = (resources.files("miniatured_world") / "assets" / "little_laboratory_background.jpg").read_bytes()
        except (FileNotFoundError, ModuleNotFoundError):
            return QPixmap()
        image = QImage()
        if not image.loadFromData(data):
            return QPixmap()
        return QPixmap.fromImage(image)

    def _load_character_sprites() -> dict[str, QPixmap]:
        sprites: dict[str, QPixmap] = {}
        try:
            base = resources.files("miniatured_world") / "assets" / "characters" / "alchemist_girl"
        except ModuleNotFoundError:
            return sprites
        for state in ("idle", "work", "success", "failure", "rest"):
            try:
                data = (base / f"{state}.png").read_bytes()
            except FileNotFoundError:
                continue
            image = QImage()
            if image.loadFromData(data):
                sprites[state] = QPixmap.fromImage(image)
        return sprites

    def _load_cauldron_sprites() -> dict[str, tuple[QPixmap, ...]]:
        sprites: dict[str, tuple[QPixmap, ...]] = {}
        try:
            base = resources.files("miniatured_world") / "assets" / "cauldron" / "magic_cauldron"
        except ModuleNotFoundError:
            return sprites
        for state in ("idle", "receive", "success", "failure"):
            frames: list[QPixmap] = []
            for index in range(1, 9):
                try:
                    data = (base / f"{state}_{index:02d}.png").read_bytes()
                except FileNotFoundError:
                    continue
                image = QImage()
                if image.loadFromData(data):
                    frames.append(QPixmap.fromImage(image))
            if not frames:
                try:
                    data = (base / f"{state}.png").read_bytes()
                except FileNotFoundError:
                    data = b""
                image = QImage()
                if data and image.loadFromData(data):
                    frames.append(QPixmap.fromImage(image))
            if frames:
                sprites[state] = tuple(frames)
        return sprites

    def _draw_lab_background(painter: QPainter, rect: QRect, background: QPixmap) -> None:
        if not background.isNull():
            source = background.rect()
            target_ratio = rect.width() / max(1, rect.height())
            source_ratio = source.width() / max(1, source.height())
            if source_ratio > target_ratio:
                width = int(source.height() * target_ratio)
                x = source.x() + (source.width() - width) // 2
                source = QRect(x, source.y(), width, source.height())
            elif source_ratio < target_ratio:
                height = int(source.width() / target_ratio)
                y = source.y() + max(0, source.height() - height) // 2
                source = QRect(source.x(), y, source.width(), height)
            painter.drawPixmap(rect, background, source)
            return

        painter.fillRect(rect, QColor("#22323b"))
        floor_top = int(rect.height() * 0.52)
        painter.fillRect(0, floor_top, rect.width(), rect.height() - floor_top, QColor("#7a5740"))
        painter.fillRect(
            int(rect.width() * 0.18),
            int(rect.height() * 0.60),
            int(rect.width() * 0.64),
            int(rect.height() * 0.28),
            QColor("#7d9488"),
        )

    def _draw_cauldron(
        painter: QPainter,
        rect: QRect,
        state: str,
        sprites: dict[str, tuple[QPixmap, ...]],
        frame_index: int,
    ) -> None:
        sprite_key = {
            "cauldron_idle": "idle",
            "cauldron_receive": "receive",
            "cauldron_success": "success",
            "cauldron_failure": "failure",
            "cauldron_react": "success",
        }.get(state, "idle")
        frames = sprites.get(sprite_key) or sprites.get("idle") or ()
        if frames:
            sprite = frames[frame_index % len(frames)]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(36, 23, 37, 70))
            painter.drawEllipse(425, 668, 145, 24)
            painter.drawPixmap(QRect(400, 444, 192, 256), sprite)
            return

        x = int(rect.width() * 0.36)
        y = int(rect.height() * 0.62)
        w = max(70, int(rect.width() * 0.14))
        h = max(58, int(rect.height() * 0.18))

        glow = {
            "cauldron_success": QColor(113, 229, 171, 105),
            "cauldron_failure": QColor(102, 96, 105, 120),
            "cauldron_react": QColor(91, 199, 188, 90),
            "cauldron_receive": QColor(88, 153, 196, 75),
        }.get(state, QColor(52, 72, 78, 45))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(x - w // 5, y - h // 3, int(w * 1.35), int(h * 0.8))

        painter.setPen(QPen(QColor("#2a2026"), 3))
        painter.setBrush(QColor("#3a2e38"))
        painter.drawRoundedRect(x, y, w, h, 18, 18)
        painter.setBrush(QColor("#11181d"))
        painter.drawEllipse(x + 8, y - 10, w - 16, 22)
        painter.setPen(QPen(QColor("#bb8e45"), 3))
        painter.drawLine(x + 14, y + h - 4, x + w - 14, y + h - 4)

    def _draw_alchemist(
        painter: QPainter,
        rect: QRect,
        state: str,
        sprites: dict[str, QPixmap],
        elapsed_ms: int,
    ) -> None:
        sprite = sprites.get(state) or sprites.get("idle")
        if sprite is not None and not sprite.isNull():
            phase = elapsed_ms / 1000
            bob = 0
            if state == "success":
                bob = -round(6 * abs(math.sin(phase * math.pi * 2)))
            elif state in {"work", "idle"}:
                bob = -round(2 * max(0, math.sin(phase * math.pi)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(36, 23, 37, 60))
            painter.drawEllipse(664, 676, 166, 16)
            painter.drawPixmap(QRect(632, 468 + bob, 230, 230), sprite)
            return

        x = int(rect.width() * 0.58)
        y = int(rect.height() * 0.58)
        scale = max(1.0, min(rect.width(), rect.height()) / 420)
        body_w = int(34 * scale)
        body_h = int(44 * scale)
        head = int(28 * scale)
        bob = -4 if state in {"success", "work"} else 0

        painter.setPen(QPen(QColor("#2b2329"), 2))
        painter.setBrush(QColor("#7b443d"))
        painter.drawEllipse(x + 2, y + body_h + bob, body_w + 12, int(10 * scale))

        painter.setBrush(QColor("#5f3f36"))
        painter.drawRoundedRect(x, y + head - 2 + bob, body_w, body_h, 8, 8)
        painter.setBrush(QColor("#e8d5bd"))
        painter.drawEllipse(x - 2, y + bob, head, head)
        painter.setBrush(QColor("#6d483e"))
        painter.drawPie(x - 10, y - 10 + bob, head + 24, int(24 * scale), 0, 180 * 16)
        painter.setBrush(QColor("#74b8c9"))
        painter.drawEllipse(x + int(7 * scale), y + int(12 * scale) + bob, 4, 4)
        painter.drawEllipse(x + int(18 * scale), y + int(12 * scale) + bob, 4, 4)

        painter.setPen(QPen(QColor("#e8d5bd"), 3))
        if state == "success":
            painter.drawLine(x + body_w, y + head + 6 + bob, x + body_w + int(15 * scale), y + head - int(8 * scale) + bob)
        elif state == "failure":
            painter.drawLine(x + body_w, y + head + 8 + bob, x + body_w + int(12 * scale), y + head + int(16 * scale) + bob)
        else:
            painter.drawLine(x + body_w, y + head + 10 + bob, x + body_w + int(14 * scale), y + head + int(3 * scale) + bob)

    def _draw_material_effects(
        painter: QPainter,
        rect: QRect,
        snapshot: WorldSnapshot,
        effects: tuple[str, ...],
        elapsed_ms: int,
    ) -> None:
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        seconds = elapsed_ms / 1000
        if "material_drop" in effects:
            material_items = [(name, count) for name, count in snapshot.materials.items() if count > 0] or [("seed", 1)]
            shapes = {
                "seed": ("000110", "001110", "011100", "111000", "010000", "100000"),
                "water": ("001000", "001100", "011100", "111110", "111110", "011100"),
                "mineral": ("001100", "011110", "111110", "111110", "011100", "001000"),
            }
            for index, (material_id, _count) in enumerate(material_items[:6]):
                progress = (seconds / 1.8 + index / 6) % 1
                x = round(300 + 196 * progress)
                y = round(516 + 61 * progress - 92 * math.sin(math.pi * progress))
                color = _WorldPreviewWidget._colors.get(material_id, QColor("#d8c998"))
                painter.setOpacity(min(1.0, progress * 8, (1 - progress) * 8))
                shape = shapes.get(material_id, ("000000", "001100", "011110", "011110", "001100", "000000"))
                for row, line in enumerate(shape):
                    for column, pixel in enumerate(line):
                        if pixel == "1":
                            shade = color.lighter(145) if row < 3 and column < 3 else color
                            painter.fillRect(x + column * 3, y + row * 3, 3, 3, shade)
                for trail in range(1, 4):
                    painter.fillRect(x - trail * 9, y + 10 + trail * 3, 3, 3, QColor(color.red(), color.green(), color.blue(), 130 // trail))
        painter.setOpacity(1)
        if "reaction_light" in effects:
            for index in range(5):
                progress = (seconds / 1.4 + index / 5) % 1
                x = round(493 + math.sin(index * 2.4 + progress) * 48)
                y = round(575 - progress * 96)
                color = QColor(154, 240, 202, round(190 * (1 - progress)))
                painter.fillRect(x - 4, y, 12, 4, color)
                painter.fillRect(x, y - 4, 4, 12, color)
        if "smoke_puff" in effects:
            for index in range(3):
                progress = (seconds / 2 + index / 3) % 1
                x = round(488 + 18 * math.sin(progress * 5 + index))
                y = round(565 - 100 * progress)
                color = QColor(154, 145, 168, round(150 * (1 - progress)))
                painter.fillRect(x, y, 16, 12, color)
                painter.fillRect(x + 4, y - 4, 12, 20, color)
        painter.restore()

    def _draw_lab_overlay(painter: QPainter, rect: QRect, snapshot: WorldSnapshot) -> None:
        panel = QRect(14, 12, min(190, rect.width() - 28), 42)
        painter.setPen(QPen(QColor(31, 41, 51, 160), 1))
        painter.setBrush(QColor(246, 247, 244, 205))
        painter.drawRoundedRect(panel, 6, 6)
        painter.setPen(QPen(QColor("#4d5a64"), 2))
        painter.drawLine(panel.x() + 18, panel.y() + 12, panel.x() + 18, panel.y() + 26)
        painter.drawLine(panel.x() + 12, panel.y() + 27, panel.x() + 24, panel.y() + 27)
        painter.setBrush(QColor("#6db2c3"))
        painter.drawEllipse(panel.x() + 10, panel.y() + 23, 16, 10)

        bar_x = panel.x() + 46
        bar_y = panel.y() + 14
        active_bars = max(1, min(5, int(round(snapshot.activity_intensity * 5))))
        for index in range(5):
            color = QColor("#6eb58f") if index < active_bars else QColor("#cad4cf")
            painter.fillRect(bar_x + index * 12, bar_y + (4 - index) * 3, 8, 8 + index * 3, color)

        material_total = min(6, sum(snapshot.materials.values()))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#d8c998"))
        for index in range(material_total):
            painter.drawEllipse(panel.x() + 122 + index * 9, panel.y() + 18 + (index % 2) * 6, 6, 6)

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

    def _apply_display_settings(window: QMainWindow) -> None:
        display = window.runtime.service.settings.display
        mode = display.view_mode
        desktop_mode = mode == "desktop"
        opacity = max(0.2, min(1.0, float(display.opacity)))
        signature = (mode, bool(display.always_on_top), bool(display.click_through), opacity)

        if getattr(window, "_display_signature", None) == signature:
            window.setWindowOpacity(opacity)
            return

        flags = Qt.WindowType.Window
        if desktop_mode:
            flags |= Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if desktop_mode or display.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint

        was_visible = window.isVisible()
        window.setWindowFlags(flags)
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, desktop_mode)
        window.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, desktop_mode and display.click_through)
        window.setWindowOpacity(opacity)
        window._display_signature = signature

        if was_visible:
            window.show()
        set_windows_click_through(int(window.winId()), desktop_mode and display.click_through)

    def _status_text(snapshot: WorldSnapshot) -> str:
        if not snapshot.running:
            return "停止"
        if snapshot.paused:
            return "一時停止中"
        if not snapshot.activity_collection_enabled:
            return "活動停止中"
        return "稼働中"

    def _provider_status_text(snapshot: WorldSnapshot) -> str:
        status = snapshot.provider_status
        if not snapshot.activity_collection_enabled:
            return "停止中"
        if not status.available:
            return f"{status.display_name}: 利用不可"
        if not status.active:
            return f"{status.display_name}: 停止"
        return status.display_name

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
            "idle": "待機",
            "work": "実験中",
            "success": "成功",
            "failure": "失敗",
            "rest": "休憩",
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
