from __future__ import annotations

from enum import StrEnum


class RuntimeCommand(StrEnum):
    SHOW_WORLD = "show_world"
    HIDE_WORLD = "hide_world"
    PAUSE = "pause"
    RESUME = "resume"
    TOGGLE_PAUSE = "toggle_pause"
    START_ACTIVITY = "start_activity"
    STOP_ACTIVITY = "stop_activity"
    MUTE = "mute"
    UNMUTE = "unmute"
    TOGGLE_MUTE = "toggle_mute"
    EXIT = "exit"

