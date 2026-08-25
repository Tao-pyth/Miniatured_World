from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True, slots=True)
class GeneralSettings:
    launch_on_login: bool = False
    minimize_to_tray: bool = True
    show_world_on_start: bool = True
    restore_window_position: bool = True
    confirm_on_exit: bool = True
    language: str = "ja"


@dataclass(frozen=True, slots=True)
class DisplaySettings:
    view_mode: str = "window"
    always_on_top: bool = False
    click_through: bool = False
    opacity: float = 1.0
    fps_limit: int = 30
    quality: str = "automatic"


@dataclass(frozen=True, slots=True)
class ActivitySettings:
    enabled: bool = True
    keyboard_enabled: bool = True
    mouse_enabled: bool = True
    click_enabled: bool = True
    scroll_enabled: bool = True
    frame_window_ms: int = 1000
    reflection_strength: float = 1.0


@dataclass(frozen=True, slots=True)
class SoundSettings:
    enabled: bool = True
    master_volume: float = 0.6
    ambience_volume: float = 0.4
    event_volume: float = 0.55


@dataclass(frozen=True, slots=True)
class NotificationSettings:
    milestone_enabled: bool = True
    rare_phenomenon_enabled: bool = True
    discovery_enabled: bool = True
    tray_enabled: bool = True
    duration_ms: int = 3500


@dataclass(frozen=True, slots=True)
class PrivacySettings:
    store_raw_input: bool = False
    store_window_titles: bool = False
    store_clipboard: bool = False
    store_screen_capture: bool = False
    external_activity_upload: bool = False


@dataclass(frozen=True, slots=True)
class PerformanceSettings:
    max_particles: int = 2000
    max_creatures: int = 24
    simulation_quality: str = "automatic"
    cpu_limit_percent: int = 10
    battery_saver: bool = True


@dataclass(frozen=True, slots=True)
class DataSettings:
    save_discovery: bool = True
    save_settings: bool = True
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class Settings:
    schema_version: int = 1
    general: GeneralSettings = field(default_factory=GeneralSettings)
    display: DisplaySettings = field(default_factory=DisplaySettings)
    activity: ActivitySettings = field(default_factory=ActivitySettings)
    sound: SoundSettings = field(default_factory=SoundSettings)
    notifications: NotificationSettings = field(default_factory=NotificationSettings)
    privacy: PrivacySettings = field(default_factory=PrivacySettings)
    performance: PerformanceSettings = field(default_factory=PerformanceSettings)
    data: DataSettings = field(default_factory=DataSettings)


def update_settings(settings: Settings, section: str, **changes: Any) -> Settings:
    if not hasattr(settings, section):
        raise ValueError(f"未知の設定セクションです: {section}")
    current_section = getattr(settings, section)
    updated_section = replace(current_section, **changes)
    return replace(settings, **{section: updated_section})
