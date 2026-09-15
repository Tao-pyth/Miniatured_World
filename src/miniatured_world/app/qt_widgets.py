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
from miniatured_world.persistence.settings import Settings, WindowSettings
from miniatured_world.app.window_placement import fit_window
from miniatured_world.persistence.log_registry import identify_log


def build_main_window(
    runtime: AppRuntime,
    *,
    duration_seconds: float | None = None,
    tick_interval_ms: int = 1000,
    stability_log: Path | None = None,
    on_stability_complete: Callable[[], None] | None = None,
    on_exit: Callable[[], None] | None = None,
):
    from PySide6.QtCore import QElapsedTimer, QEvent, QPoint, QRect, QSignalBlocker, Qt, QTimer
    from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QPixmapCache
    from miniatured_world.app.lab_layout import DEFAULT_LAYOUT
    from miniatured_world.app.lab_paint import draw_lab_scene, load_props
    from miniatured_world.app.lab_hands import load_hand_assets
    from miniatured_world.app.hand_motion import motion_data, motion_clip
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFormLayout,
        QFileDialog,
        QDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QPlainTextEdit,
        QScrollArea,
        QSlider,
        QSpinBox,
        QStyle,
        QSystemTrayIcon,
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
            self._props = load_props()
            self._hand_assets = load_hand_assets()
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

        def clear_cache(self) -> bool:
            try:
                motion_data.__wrapped__()  # 再読込可能かを先に確認し、失敗時の表示を保つ。
                background = _load_lab_background()
                characters = _load_character_sprites()
                cauldron = _load_cauldron_sprites()
                props, hands = load_props(), load_hand_assets()
                if background.isNull() or not self._character_sprites.keys() <= characters.keys() or any(len(cauldron.get(key, ())) < len(frames) for key, frames in self._cauldron_sprites.items()):
                    raise ValueError("画像を読み直せません。")
            except (OSError, ValueError, RuntimeError):
                return False
            self._background, self._character_sprites, self._cauldron_sprites = background, characters, cauldron
            self._props, self._hand_assets = props, hands
            QPixmapCache.clear()
            motion_clip.cache_clear()
            motion_data.cache_clear()
            self.update()
            return True

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
            draw_lab_scene(painter, DEFAULT_LAYOUT, self._props, self._character_sprites, self._cauldron_sprites, scene, self.animation.elapsed_ms, self.animation.frame_index, hand_assets=self._hand_assets)

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
        def __init__(self, runtime: AppRuntime, request_exit: Callable[[], bool]) -> None:
            super().__init__()
            self._runtime = runtime
            self._request_exit = request_exit
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
            self.status.setToolTip(snapshot.provider_status.detail if snapshot.system_paused else "")
            self.pause_button.setText("再開" if self._runtime.state.paused else "一時停止")
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
            if command == RuntimeCommand.EXIT:
                self._request_exit()
            else:
                self._runtime.handle(command)

    class _SettingsTab(QWidget):
        def __init__(self, settings: Settings, runtime: AppRuntime, on_delete: Callable[[str], None]) -> None:
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
            tabs.addTab(_data_settings(settings, runtime, on_delete), "データ")
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

        def refresh(self, discoveries: tuple[str, ...]) -> None:
            self.list_widget.clear()
            if not discoveries:
                self.list_widget.addItem("発見なし")
            else:
                for discovery in discoveries:
                    self.list_widget.addItem(_display_value(discovery))
            self.summary.setText(f"{len(discoveries)}件の発見")

    class _MiniaturedWorldMainWindow(QMainWindow):
        def __init__(self, runtime: AppRuntime) -> None:
            super().__init__()
            self.runtime = runtime
            self._geometry_ready = False
            self._applying_display = False
            saved_window = runtime.service.settings.window
            self._normal_placement: WindowSettings | None = (
                saved_window if saved_window.saved and runtime.service.settings.general.restore_window_position else None
            )
            self._first_show = True
            self.geometry_timer = QTimer(self)
            self.geometry_timer.setSingleShot(True)
            self.geometry_timer.setInterval(300)
            self.geometry_timer.timeout.connect(self._save_window_placement)
            self._shutting_down = False
            self._quit_requested = False
            self._hidden_to_tray = False
            self._exit_dialog = None
            self._requested_tick_ms = tick_interval_ms
            self._tick_interval_ms = runtime.service.effective_tick_ms(tick_interval_ms)
            self._stability_elapsed_ms = 0
            self._stability_frame = 0
            self._stability_completed = False
            self._stability_duration_ms = (
                None if duration_seconds is None else max(1, math.ceil(duration_seconds * 1000))
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
                    registry=runtime.service.log_registry,
                )
            )
            self._on_stability_complete = on_stability_complete
            self._display_signature: tuple[str, bool, bool, float] | None = None
            self.setWindowTitle("小さなラボラトリー")
            self.setMinimumSize(900, 620)

            self.tabs = QTabWidget()
            self.world_tab = _WorldTab(runtime, self.request_exit)
            self.settings_tab = _SettingsTab(runtime.service.settings, runtime, self._delete_saved_data)
            self.discovery_tab = _DiscoveryTab()
            self.tabs.addTab(self.world_tab, "ラボ")
            self.tabs.addTab(self.settings_tab, "設定")
            self.tabs.addTab(self.discovery_tab, "発見")
            # 高DPIや画面縮小時にもラボ/設定の操作へスクロールで到達できる。
            self.content_scroll = QScrollArea()
            self.content_scroll.setWidgetResizable(True)
            self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
            self.content_scroll.setWidget(self.tabs)
            self.setCentralWidget(self.content_scroll)
            self.setStyleSheet(_style_sheet())
            self.storage_notice = QLabel()
            self.storage_notice.setObjectName("storage_notice")
            self.storage_notice.setWordWrap(True)
            self.storage_notice.setStyleSheet("color:#302b25; background:#f2e6cb; padding:8px;")
            self.statusBar().addWidget(self.storage_notice, 1)
            self.data_result = QLabel()
            self.data_result.setObjectName("data_delete_result")
            self.data_result.setWordWrap(True)
            self.statusBar().addWidget(self.data_result, 1)
            self._data_result_lines: list[str] = []
            self.data_details = QPushButton("削除結果の詳細")
            self.data_details.setObjectName("data_delete_details")
            self.data_details.clicked.connect(self._show_data_details)
            self.data_details.hide()
            self.statusBar().addPermanentWidget(self.data_details)
            _apply_display_settings(self)

            self.timer = QTimer(self)
            self.timer.timeout.connect(self.advance)
            self.timer.start(self._tick_interval_ms)
            snapshot = runtime.snapshot()
            self.refresh(snapshot)
            placement = runtime.service.settings.window if runtime.service.settings.general.restore_window_position else WindowSettings()
            self._fit_placement(placement)
            self._geometry_ready = True
            if self._stability_logger is not None:
                self._stability_logger.start(snapshot)

        def advance(self) -> None:
            if self._shutting_down:
                return
            try:
                elapsed = self._tick_interval_ms
                snapshot = self.runtime.tick(elapsed_ms=elapsed)
                self._stability_elapsed_ms += elapsed
                self._stability_frame += 1
                self.refresh(snapshot)
                if self._stability_logger is not None:
                    self._stability_logger.tick(self._stability_frame, snapshot, self.runtime.service.summary_text(), elapsed_ms=elapsed)
                if self._stability_duration_ms is not None and self._stability_elapsed_ms >= self._stability_duration_ms:
                    self._complete_stability_run(snapshot)
                    return
                if not snapshot.running:
                    self.shutdown()
                    self._quit_application()
            except BaseException as error:
                if self._stability_logger is not None:
                    self._stability_logger.error(error)
                    self._stability_logger.close()
                raise

        def refresh(self, snapshot: WorldSnapshot) -> None:
            if self._shutting_down:
                return
            if self._hidden_to_tray and not self._tray_available():
                self.showNormal()
            interval = self.runtime.service.effective_tick_ms(self._requested_tick_ms)
            if interval != self._tick_interval_ms:
                self._tick_interval_ms = interval
                self.timer.setInterval(interval)
            _apply_display_settings(self)
            self.world_tab.refresh(snapshot)
            self.discovery_tab.refresh(tuple(sorted(self.runtime.service.discovery_manager.discoveries)))
            store = self.runtime.service.store
            messages = "\n".join(issue.message for issue in store.issues) if store else ""
            if self.runtime.service.log_registry.registration_failed:
                messages += "\nログを管理一覧に登録できませんでした。過去ログの選択から対象を確認してください。"
            self.storage_notice.setText(messages)
            self.storage_notice.setVisible(bool(messages))

        def showEvent(self, event) -> None:  # noqa: N802
            super().showEvent(event)
            self._hidden_to_tray = False
            if self._first_show:
                self._first_show = False
                QTimer.singleShot(0, self._fit_after_show)
            self.world_tab.refresh(self.runtime.snapshot())
            # 再表示は同じセッションを再開する。終了済みの実行は復活させない。
            timer = getattr(self, "timer", None)
            if (
                timer is not None
                and self.runtime.state.running
                and not self._stability_completed
                and not timer.isActive()
            ):
                timer.start(self._tick_interval_ms)

        def _read_placement(self) -> WindowSettings:
            handle = self.windowHandle()
            position = handle.framePosition() if handle is not None else self.pos()
            return WindowSettings(True, position.x(), position.y(), self.width(), self.height())

        def _normal_window(self) -> bool:
            return bool(
                self._geometry_ready and not self._applying_display
                and self.isVisible() and not self.isMinimized()
                and not self.isMaximized() and not self.isFullScreen()
                and self.runtime.service.settings.display.view_mode != "desktop"
            )

        def _fit_placement(self, placement: WindowSettings) -> None:
            screens = QApplication.screens()
            primary = QApplication.primaryScreen()
            screens.sort(key=lambda screen: screen != primary)
            areas = [(area.x(), area.y(), area.width(), area.height()) for screen in screens if (area := screen.availableGeometry()).isValid()]
            handle = self.windowHandle()
            margins = handle.frameMargins() if handle is not None else None
            frame = (margins.left(), margins.top(), margins.right(), margins.bottom()) if margins else (0, 0, 0, 0)
            fitted = fit_window(placement, areas, frame=frame)
            if not fitted.saved:
                return
            self.setMinimumSize(min(900, fitted.width), min(620, fitted.height))
            self.resize(fitted.width, fitted.height)
            if handle is not None:
                handle.setFramePosition(QPoint(fitted.x, fitted.y))
            else:
                self.move(fitted.x, fitted.y)

        def _fit_after_show(self) -> None:
            if self._shutting_down or not self.isVisible():
                return
            # OSがフレーム寸法を確定した後、タスクバーへのはみ出しを補正。
            self._fit_placement(self._read_placement())
            self._schedule_window_save()

        def moveEvent(self, event) -> None:  # noqa: N802
            super().moveEvent(event)
            self._schedule_window_save()

        def resizeEvent(self, event) -> None:  # noqa: N802
            super().resizeEvent(event)
            self._schedule_window_save()

        def _schedule_window_save(self) -> None:
            if self._shutting_down or not self._normal_window():
                return
            self._normal_placement = self._read_placement()
            self.geometry_timer.start()

        def _save_window_placement(self) -> None:
            self.geometry_timer.stop()
            if self._normal_window():
                self._normal_placement = self._read_placement()
            if self._normal_placement is not None:
                self.runtime.service.remember_window(self._normal_placement)

        def _delete_saved_data(self, target: str) -> None:
            if self.runtime.service.store is None and target != "cache":
                return
            registry = self.runtime.service.log_registry
            labels = {"settings": "設定", "discovery": "発見データ", "settings_and_discovery": "設定と発見データ", "logs": "管理しているログ", "selected_logs": "選択したログ", "cache": "キャッシュ", "all": "すべてのアプリケーションデータ"}
            entries = {entry.path: entry for entry in registry.entries} if target in ("logs", "all") else {}
            rejected = set()
            def select_logs() -> bool:
                paths, _ = QFileDialog.getOpenFileNames(self, "削除する過去ログを選択", "", "診断ログ (*.jsonl);;すべてのファイル (*)")
                for name in paths:
                    try:
                        entry = identify_log(Path(name))
                    except (OSError, ValueError, UnicodeError):
                        rejected.add(name)
                    else:
                        entries[entry.path] = entry
                return bool(paths)
            if target == "selected_logs" and not select_logs():
                return
            while True:
                dialog = QMessageBox(self)
                dialog.setObjectName("data_delete_confirmation")
                dialog.setWindowTitle(f"{labels[target]}の削除")
                dialog.setIcon(QMessageBox.Icon.Warning)
                detail = "現在のラボは続きます。"
                if target in ("settings", "discovery", "settings_and_discovery", "all"):
                    detail += "削除した種類の保存はOFFになり、設定からONにできます。"
                if target in ("settings", "settings_and_discovery", "all"):
                    detail += "設定を初期化し、活動取得もOFFにします。ログイン時の起動登録も解除します。解除できない場合は設定を残します。"
                if target in ("logs", "selected_logs", "all"):
                    detail += f"\n対象ログ: {len(entries)}件。ログ出力を停止して削除します。"
                    detail += "\n未登録の過去ログは「過去ログを追加」から選択できます。未知のファイルは自動探索しません。"
                    if registry.protected:
                        detail += "\n管理一覧を読めないため、一部の過去ログの所在を確認できません。一覧を保護し、全ログの削除済みとは扱いません。"
                if target in ("cache", "all"):
                    detail += "\n画像と動作のキャッシュを読み直します。同梱の元画像は削除しません。"
                if target == "all":
                    detail += "\n設定・発見・ログ・ログ管理一覧・保存用一時ファイル・キャッシュが対象です。"
                if rejected:
                    detail += f"\nログ形式を確認できない選択ファイル{len(rejected)}件は削除しません。"
                detail += "\n" + "\n".join(list(entries)[:5])
                dialog.setText(f"{labels[target]}を削除しますか？ 元に戻せません。\n\n{detail}")
                if len(entries) > 5:
                    dialog.setDetailedText("\n".join(entries))
                    for button in dialog.buttons():
                        button.setText("対象の一覧")
                        button.clicked.connect(lambda checked=False, item=button: item.setText("対象の一覧"))
                erase = dialog.addButton("削除する", QMessageBox.ButtonRole.DestructiveRole)
                cancel = dialog.addButton("キャンセル", QMessageBox.ButtonRole.RejectRole)
                add = dialog.addButton("過去ログを追加", QMessageBox.ButtonRole.ActionRole) if target in ("logs", "selected_logs", "all") else None
                dialog.setDefaultButton(cancel)
                dialog.setEscapeButton(cancel)
                dialog.exec()
                clicked = dialog.clickedButton()
                dialog.deleteLater()
                if add is not None and clicked == add:
                    select_logs()
                    continue
                if clicked != erase:
                    return
                break
            result = {name: False for name in rejected}
            if target in ("logs", "selected_logs", "all"):
                result.update(registry.delete(entries.values()))
                if registry.registration_failed:
                    result["log_registration"] = False
            if target in ("settings", "discovery", "settings_and_discovery", "all"):
                result.update(self.runtime.delete_saved_data("settings_and_discovery" if target == "all" else target))
                if result.get("settings.json"):
                    self.geometry_timer.stop()
                    self._normal_placement = None
            if target in ("cache", "all"):
                result["cache"] = self.world_tab.preview.clear_cache()
            messages = []
            for name, success in result.items():
                if name == "startup":
                    messages.append("ログイン時の起動登録を解除しました。" if success else "ログイン時の起動登録を解除できませんでした。設定を残しています。")
                    continue
                label = {"settings.json": "設定", "discovery.json": "発見データ", "log-index.json": "ログ管理一覧", "cache": "キャッシュ", "log_registration": "所在を確認できないログ"}.get(name, f"ログ（{name}）")
                messages.append(f"{label}を削除しました。" if success else f"{label}を削除できませんでした。")
            self._data_result_lines = messages
            if len(messages) > 6:
                failed = sum(not value for value in result.values())
                self.data_result.setText(f"削除結果: 成功{len(result) - failed}件、未完了{failed}件。対象別の結果は詳細から確認できます。")
            else:
                self.data_result.setText("\n".join(messages))
            self.data_details.setVisible(len(messages) > 6)
            previous = self.settings_tab
            self.tabs.removeTab(1)
            self.settings_tab = _SettingsTab(self.runtime.service.settings, self.runtime, self._delete_saved_data)
            self.tabs.insertTab(1, self.settings_tab, "設定")
            self.tabs.setCurrentIndex(1)
            inner = self.settings_tab.findChild(QTabWidget)
            inner.setCurrentIndex(inner.count() - 1)
            previous.deleteLater()
            self.refresh(self.runtime.snapshot())

        def _show_data_details(self) -> None:
            dialog = QDialog(self)
            dialog.setWindowTitle("削除結果の詳細")
            layout = QVBoxLayout(dialog)
            text = QPlainTextEdit()
            text.setReadOnly(True)
            text.setPlainText("\n".join(self._data_result_lines))
            layout.addWidget(text)
            close = QPushButton("閉じる")
            close.clicked.connect(dialog.accept)
            layout.addWidget(close)
            dialog.resize(680, 400)
            dialog.exec()
            dialog.deleteLater()

        def _tray_available(self) -> bool:
            tray = getattr(self, "tray", None)
            return bool(tray is not None and tray.isVisible() and QSystemTrayIcon.isSystemTrayAvailable())

        def eventFilter(self, watched, event) -> bool:  # noqa: N802
            # QApplication.quitはaboutToQuitより先にウィンドウを閉じる。
            # そのcloseを利用者操作と誤認して確認を出さない。
            if watched is QApplication.instance() and event.type() == QEvent.Type.Quit:
                self.shutdown()
            return super().eventFilter(watched, event)

        def hide_to_tray(self) -> None:
            if self._shutting_down:
                return
            if self._tray_available():
                self._save_window_placement()
                self._hidden_to_tray = True
                self.hide()
            else:
                self.showNormal()

        def request_exit(self) -> bool:
            if self._shutting_down:
                return True
            if self._exit_dialog is not None:
                self._exit_dialog.raise_()
                self._exit_dialog.activateWindow()
                return False
            if self.runtime.state.running and self.runtime.service.settings.general.confirm_on_exit:
                dialog = QMessageBox(self)
                self._exit_dialog = dialog
                dialog.setObjectName("exit_confirmation")
                dialog.setWindowTitle("アプリケーションの終了")
                dialog.setIcon(QMessageBox.Icon.Question)
                dialog.setText("小さなラボラトリーを終了しますか？\n現在のラボは終了します。設定と発見は保存設定に従って保持されます。")
                confirm = dialog.addButton("終了する", QMessageBox.ButtonRole.AcceptRole)
                cancel = dialog.addButton("キャンセル", QMessageBox.ButtonRole.RejectRole)
                dialog.setDefaultButton(cancel)
                dialog.setEscapeButton(cancel)
                def finish_confirmation(_result):
                    accepted = dialog.clickedButton() == confirm
                    self._exit_dialog = None
                    dialog.deleteLater()
                    if accepted and not self._shutting_down:
                        self.shutdown()
                        self._quit_application()
                dialog.finished.connect(finish_confirmation)
                dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
                # 非同期表示で、支援技術のボタン呼出し中にネストした
                # イベントループを保持して確認画面への操作を塞がない。
                dialog.show()
                return False
            self.shutdown()
            self._quit_application()
            return True

        def _quit_application(self) -> None:
            if self._quit_requested:
                return
            self._quit_requested = True
            callback = on_exit or QApplication.instance().quit
            callback()

        def shutdown(self) -> None:
            """確認を伴わない冪等な後始末。Qtの終了通知とテストにも使用する。"""
            if self._shutting_down:
                return
            self._save_window_placement()
            self._shutting_down = True
            if self._exit_dialog is not None:
                self._exit_dialog.reject()
            self.runtime.stop()
            self.timer.stop()
            self.world_tab.preview.animation_timer.stop()
            self._close_stability_log(cancelled=True)
            tray = getattr(self, "tray", None)
            if tray is not None:
                tray.hide()
            self.close()

        def closeEvent(self, event) -> None:  # noqa: N802
            if self._shutting_down:
                event.accept()
            elif not self.runtime.state.running or QApplication.instance().isSavingSession():
                self.shutdown()
                self._quit_application()
                event.accept()
            elif self.runtime.service.settings.general.minimize_to_tray and self._tray_available():
                self.hide_to_tray()
                event.ignore()
            elif self.request_exit():
                event.accept()
            else:
                event.ignore()

        def _complete_stability_run(self, snapshot: WorldSnapshot) -> None:
            if self._stability_completed:
                return
            self._stability_completed = True
            self.shutdown()
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
                self._quit_application()

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
            data = (resources.files("miniatured_world") / "assets" / "little_laboratory_background.png").read_bytes()
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
        for asset in sorted(base.iterdir(), key=lambda path: path.name):
            if not asset.name.endswith(".png"):
                continue
            state = asset.name.removesuffix(".png")
            try:
                data = asset.read_bytes()
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

    def _group(title: str, rows: list[tuple[str, object]]) -> QWidget:
        box = QGroupBox(title)
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        for label, widget in rows:
            if hasattr(widget, "setObjectName") and not widget.objectName():
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
            "マウス移動": "mouse",
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
        launch = QCheckBox("登録する")
        launch.setObjectName("general_launch_on_login")
        startup_notice = QLabel()
        startup_notice.setObjectName("startup_status")
        startup_notice.setWordWrap(True)
        retry = QPushButton("登録状態を再確認")
        retry.setObjectName("startup_refresh")

        def show_startup(status) -> None:
            with QSignalBlocker(launch):
                launch.setTristate(status.registered is None)
                launch.setCheckState(Qt.CheckState.PartiallyChecked if status.registered is None else Qt.CheckState.Checked if status.registered else Qt.CheckState.Unchecked)
                launch.setEnabled(status.can_change)
            startup_notice.setText(status.message)

        def change_startup(enabled: bool) -> None:
            show_startup(runtime.set_launch_on_login(enabled))

        launch.toggled.connect(change_startup)
        retry.clicked.connect(lambda: show_startup(runtime.startup.inspect()))
        show_startup(runtime.startup.inspect())
        return _group(
            "一般",
            [
                ("ログイン時に起動", launch),
                ("登録状態", startup_notice),
                ("", retry),
                ("起動設定について", QLabel("登録はWindows側へ保存します。設定の保存OFFでも保持されます。\nアプリを移動した場合は、一度OFFにしてからONにしてください。")),
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
                ("マウス移動", _check(settings.activity.mouse_enabled, on_change=_setting(runtime, "activity", "mouse_enabled"))),
                ("クリック", _check(settings.activity.click_enabled, on_change=_setting(runtime, "activity", "click_enabled"))),
                ("スクロール", _check(settings.activity.scroll_enabled, on_change=_setting(runtime, "activity", "scroll_enabled"))),
                ("集約間隔ms", _spin(settings.activity.frame_window_ms, 100, 5000, 100, on_change=_setting(runtime, "activity", "frame_window_ms"))),
                ("反映量", _slider(settings.activity.reflection_strength, on_change=_setting(runtime, "activity", "reflection_strength", lambda value: int(value) / 100.0))),
                ("種類の選択", QLabel("4種類は独立して選べます。\nOFFにした種類はラボへ反映しません。")),
                ("反映量の意味", QLabel("0では活動を反映せず、ラボは自然に進行します。\n取得を止める場合は「有効」をOFFにしてください。")),
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

    def _data_settings(settings: Settings, runtime: AppRuntime, on_delete: Callable[[str], None]) -> QWidget:
        rows = [
            ("発見を保存", _check(settings.data.save_discovery, on_change=_setting(runtime, "data", "save_discovery"))),
            ("設定を保存", _check(settings.data.save_settings, on_change=_setting(runtime, "data", "save_settings"))),
            ("スキーマバージョン", _spin(settings.data.schema_version, 1, 99, 1)),
        ]
        for target, label in (("discovery", "発見データを削除"), ("settings", "設定を削除・初期化"), ("settings_and_discovery", "設定と発見データを削除"), ("logs", "ログを削除"), ("selected_logs", "過去のログを選んで削除"), ("cache", "キャッシュを削除"), ("all", "すべてのアプリデータを削除")):
            button = QPushButton(label)
            button.setObjectName(f"delete_{target}")
            button.setEnabled(runtime.service.store is not None or target == "cache")
            button.clicked.connect(lambda checked=False, selected=target: on_delete(selected))
            rows.append(("", button))
        explanation = QLabel("削除前に対象を確認します。未登録の過去ログは選択して追加できます。" if runtime.service.store else "一時実行中は既存の保存先に触れません。キャッシュのみ削除できます。")
        explanation.setWordWrap(True)
        rows.append(("", explanation))
        return _group(
            "データ",
            rows,
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

        previous_signature = window._display_signature
        previous_placement = window._normal_placement
        # 設定値は先に変わるため、直前の表示モードでも通常位置を判定する。
        if previous_signature and previous_signature[0] != "desktop" and window.isVisible() and not window.isMinimized() and not window.isMaximized() and not window.isFullScreen():
            previous_placement = window._read_placement()
        if previous_placement is not None:
            window._normal_placement = previous_placement
        was_visible = window.isVisible()
        window._applying_display = True
        window.setWindowFlags(flags)
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, desktop_mode)
        window.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, desktop_mode and display.click_through)
        window.setWindowOpacity(opacity)
        window._display_signature = signature

        if was_visible:
            window.show()
        set_windows_click_through(int(window.winId()), desktop_mode and display.click_through)
        if not desktop_mode and previous_placement is not None:
            window._fit_placement(previous_placement)
        window._applying_display = False

    def _status_text(snapshot: WorldSnapshot) -> str:
        if not snapshot.running:
            return "停止"
        if snapshot.system_paused:
            return "PC状態による休止中"
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
