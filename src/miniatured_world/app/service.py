from __future__ import annotations

from dataclasses import dataclass, field, replace
from collections import deque
from pathlib import Path
from typing import Any

from miniatured_world.activity import ActivityAggregator, PrivacyFilter
from miniatured_world.activity.models import ActivityFrame, ActivitySelection
from miniatured_world.persistence import DiscoveryManager, JsonStore, Settings, update_settings
from miniatured_world.world import WorldSession, WorldSimulation
from miniatured_world.persistence.log_registry import LogRegistry
from miniatured_world.persistence.settings import WindowSettings


_SUMMARY_LABELS = {
    "forest": "森",
    "wetland": "湿地",
    "desert": "砂漠",
    "crystal": "結晶",
}


@dataclass(slots=True)
class MiniaturedWorldService:
    simulation: WorldSimulation
    aggregator: ActivityAggregator = field(default_factory=ActivityAggregator)
    privacy_filter: PrivacyFilter = field(default_factory=PrivacyFilter)
    settings: Settings = field(default_factory=Settings)
    store: JsonStore | None = None
    discovery_manager: DiscoveryManager = field(default_factory=DiscoveryManager)
    now_ms: int = 0
    log_registry: LogRegistry = field(init=False)
    _next_activity_ms: int = field(default=1000, init=False)
    _next_world_ms: int = field(default=1000, init=False)
    _persistence_initialized: bool = field(default=False, init=False)
    _activity_windows: deque[tuple[int, ActivityFrame]] = field(default_factory=deque, init=False)
    _display_frame: ActivityFrame = field(default_factory=ActivityFrame.quiet, init=False)

    def __post_init__(self) -> None:
        self.log_registry = LogRegistry(self.store)
        self._apply_activity_selection()
        self.reset_activity()

    def _apply_activity_selection(self) -> None:
        activity = self.settings.activity
        selection = ActivitySelection(
            activity.keyboard_enabled, activity.mouse_enabled,
            activity.click_enabled, activity.scroll_enabled,
        )
        window_ms = max(100, min(5000, activity.frame_window_ms))
        if selection != self.aggregator.selection or window_ms != self.aggregator.frame_window_ms:
            self.aggregator.selection = selection
            self.aggregator.frame_window_ms = window_ms
            self.reset_activity()

    def reset_activity(self) -> None:
        self.aggregator.discard_pending()
        self._activity_windows.clear()
        self._display_frame = ActivityFrame.quiet(self.now_ms / 1000.0)
        self._next_activity_ms = self.now_ms + self.aggregator.frame_window_ms

    def effective_tick_ms(self, requested_ms: int) -> int:
        if requested_ms <= 0:
            raise ValueError("更新間隔は正のミリ秒で指定してください。")
        return min(requested_ms, self.aggregator.frame_window_ms)

    def _consume_world_frame(self, world_ms: int) -> ActivityFrame:
        names = ("keyboard_activity", "pointer_activity", "click_activity", "scroll_activity", "burstiness", "continuity")
        values = dict.fromkeys(names, 0.0)
        idle_deficit = 0.0
        remaining = 1000
        while remaining and self._activity_windows:
            duration, frame = self._activity_windows.popleft()
            used = min(remaining, duration)
            weight = used / 1000.0
            for name in names:
                values[name] += getattr(frame, name) * weight
            idle_deficit += (1.0 - frame.idle_ratio) * weight
            remaining -= used
            if used < duration:
                self._activity_windows.appendleft((duration - used, frame))
        values = {name: min(1.0, max(0.0, value)) for name, value in values.items()}
        return ActivityFrame(
            **values, idle_ratio=max(0.0, 1.0 - idle_deficit), session_duration=world_ms / 1000.0,
        ).with_strength(self.settings.activity.reflection_strength)

    @classmethod
    def start(cls, seed: int, data_root: Path | None = None) -> "MiniaturedWorldService":
        store = JsonStore(data_root) if data_root else None
        settings = store.load_settings() if store else Settings()
        discovery_manager = DiscoveryManager.load(store)
        session = WorldSession.create(seed)
        return cls(
            simulation=WorldSimulation(session),
            settings=settings,
            store=store,
            discovery_manager=discovery_manager,
        )

    def inject_demo_activity(self, frame_index: int) -> None:
        base = self.now_ms
        for offset, key in enumerate(("a", "b", "1", " ", "Enter")):
            self.aggregator.add(self.privacy_filter.keyboard(key, base + offset * 30))
        self.aggregator.add(self.privacy_filter.pointer_move(120 + frame_index * 5, 40, base + 180))
        if frame_index % 2 == 0:
            self.aggregator.add(self.privacy_filter.pointer_click(base + 220))
        if frame_index % 3 == 0:
            self.aggregator.add(self.privacy_filter.idle(base + 300, 10_000))

    def step(self, elapsed_ms: int = 1000):
        if elapsed_ms <= 0:
            raise ValueError("経過時間は正のミリ秒で指定してください。")
        target_ms = self.now_ms + elapsed_ms
        world_updated = False
        while min(self._next_activity_ms, self._next_world_ms) <= target_ms:
            boundary = min(self._next_activity_ms, self._next_world_ms)
            if boundary == self._next_activity_ms:
                frame = replace(self.aggregator.frame(boundary), session_duration=boundary / 1000.0)
                self._display_frame = frame
                self._activity_windows.append((self.aggregator.frame_window_ms, frame))
                self._next_activity_ms += self.aggregator.frame_window_ms
            if boundary == self._next_world_ms:
                self.simulation.step(self._consume_world_frame(boundary))
                self._next_world_ms += 1000
                world_updated = True
        self.now_ms = target_ms
        if world_updated or not self._persistence_initialized:
            self._persistence_initialized = True
            self._save_settings()
            self.discovery_manager.merge(
                self.simulation.session.state.discoveries,
                persist=self.settings.data.save_discovery,
            )
        self.retry_pending_saves()
        return self._display_frame.with_strength(self.settings.activity.reflection_strength)

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings
        self._apply_activity_selection()
        if self.store and not settings.data.save_discovery:
            self.store.cancel_pending_discovery()
        self._save_settings(force=True)

    def update_setting(self, section: str, field_name: str, value: Any) -> None:
        if self.store and section == "data" and bool(value):
            if field_name == "save_settings":
                self.store.resume_saving("settings.json")
            elif field_name == "save_discovery":
                self.store.resume_saving("discovery.json")
        self.update_settings(update_settings(self.settings, section, **{field_name: value}))

    def delete_saved_data(self, target: str) -> dict[str, bool]:
        if target not in ("settings", "discovery", "settings_and_discovery"):
            raise ValueError("削除対象が不明です。")
        if self.store is None:
            return {}
        names = ("discovery.json", "settings.json") if target == "settings_and_discovery" else (f"{target}.json",)
        result = {}
        for name in names:
            result[name] = self.store.delete_data(name)
            if not result[name]:
                continue
            if name == "discovery.json":
                self.discovery_manager.forget(self.simulation.session.state.discoveries)
                self.settings = replace(self.settings, data=replace(self.settings.data, save_discovery=False))
            else:
                defaults = Settings()
                self.settings = replace(
                    defaults, activity=replace(defaults.activity, enabled=False),
                    data=replace(defaults.data, save_settings=False, save_discovery=self.settings.data.save_discovery),
                )
                self._apply_activity_selection()
                self.reset_activity()
        self._save_settings(force=True)
        return result

    def remember_window(self, placement: WindowSettings) -> None:
        # 自動位置更新は明示的設定変更のforce保存を使わない。
        if (
            self.store is None or not self.settings.data.save_settings
            or not self.settings.general.restore_window_position
            or self.store.is_read_protected("settings.json")
            or placement == self.settings.window
        ):
            return
        self.settings = replace(self.settings, window=placement)
        self._save_settings()

    def _save_settings(self, *, force: bool = False) -> None:
        if self.store and (force or self.settings.data.save_settings):
            self.store.save_settings(self.settings)

    def retry_pending_saves(self, *, force: bool = False) -> None:
        if self.store:
            if not self.settings.data.save_discovery:
                self.store.cancel_pending_discovery()
            self.store.retry_pending(force=force)

    def summary_text(self) -> str:
        summary = self.simulation.summary()
        return (
            f"小さなラボラトリー シード={summary['seed']} "
            f"傾向={_SUMMARY_LABELS.get(str(summary['tendency']), summary['tendency'])} "
            f"発見={len(summary['discoveries'])} "
            f"イベント={len(summary['events'])}"
        )
