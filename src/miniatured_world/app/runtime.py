from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from miniatured_world.activity import ActivityFrame, ActivityProvider, ActivityProviderStatus, NullActivityProvider
from miniatured_world.app.commands import RuntimeCommand
from miniatured_world.app.service import MiniaturedWorldService
from miniatured_world.app.snapshot import WorldSnapshot


@dataclass(slots=True)
class RuntimeState:
    running: bool = True
    paused: bool = False
    world_visible: bool = True
    muted: bool = False
    activity_collection_enabled: bool = True
    last_frame: ActivityFrame = field(default_factory=ActivityFrame.quiet)


@dataclass(slots=True, weakref_slot=True)
class AppRuntime:
    service: MiniaturedWorldService
    provider: ActivityProvider = field(default_factory=NullActivityProvider)
    state: RuntimeState = field(default_factory=RuntimeState)

    @classmethod
    def start(
        cls,
        seed: int,
        provider: ActivityProvider | None = None,
        data_root: Path | None = None,
    ) -> "AppRuntime":
        service = MiniaturedWorldService.start(seed=seed, data_root=data_root)
        state = RuntimeState(
            world_visible=service.settings.general.show_world_on_start,
            muted=not service.settings.sound.enabled,
            activity_collection_enabled=service.settings.activity.enabled,
        )
        return cls(
            service=service,
            provider=provider or NullActivityProvider(),
            state=state,
        )

    def pause(self) -> None:
        self.state.paused = True

    def resume(self) -> None:
        self.state.paused = False

    def stop(self) -> None:
        self.state.running = False

    def set_activity_collection(self, enabled: bool) -> None:
        self.state.activity_collection_enabled = enabled
        self.service.update_setting("activity", "enabled", enabled)

    def show_world(self) -> None:
        self.state.world_visible = True

    def hide_world(self) -> None:
        self.state.world_visible = False

    def mute(self) -> None:
        self.state.muted = True
        self.service.update_setting("sound", "enabled", False)

    def unmute(self) -> None:
        self.state.muted = False
        self.service.update_setting("sound", "enabled", True)

    def update_setting(self, section: str, field_name: str, value: Any) -> None:
        self.service.update_setting(section, field_name, value)
        if section == "activity" and field_name == "enabled":
            self.state.activity_collection_enabled = bool(value)
        if section == "sound" and field_name == "enabled":
            self.state.muted = not bool(value)

    def handle(self, command: RuntimeCommand | str) -> WorldSnapshot:
        runtime_command = RuntimeCommand(command)
        if runtime_command == RuntimeCommand.SHOW_WORLD:
            self.show_world()
        elif runtime_command == RuntimeCommand.HIDE_WORLD:
            self.hide_world()
        elif runtime_command == RuntimeCommand.PAUSE:
            self.pause()
        elif runtime_command == RuntimeCommand.RESUME:
            self.resume()
        elif runtime_command == RuntimeCommand.TOGGLE_PAUSE:
            self.state.paused = not self.state.paused
        elif runtime_command == RuntimeCommand.START_ACTIVITY:
            self.set_activity_collection(True)
        elif runtime_command == RuntimeCommand.STOP_ACTIVITY:
            self.set_activity_collection(False)
        elif runtime_command == RuntimeCommand.MUTE:
            self.mute()
        elif runtime_command == RuntimeCommand.UNMUTE:
            self.unmute()
        elif runtime_command == RuntimeCommand.TOGGLE_MUTE:
            if self.state.muted:
                self.unmute()
            else:
                self.mute()
        elif runtime_command == RuntimeCommand.EXIT:
            self.stop()
        return self.snapshot()

    def tick(self, elapsed_ms: int = 1000) -> WorldSnapshot:
        if not self.state.running or self.state.paused:
            return self.snapshot()

        next_now = self.service.now_ms + elapsed_ms
        if self.state.activity_collection_enabled:
            for event in self.provider.poll(next_now):
                self.service.aggregator.add(event)

        self.state.last_frame = self.service.step(elapsed_ms=elapsed_ms)
        return self.snapshot()

    def snapshot(self) -> WorldSnapshot:
        return WorldSnapshot.from_simulation(
            self.service.simulation,
            self.state.last_frame,
            running=self.state.running,
            paused=self.state.paused,
            world_visible=self.state.world_visible,
            muted=self.state.muted,
            activity_collection_enabled=self.state.activity_collection_enabled,
            provider_status=self.provider_status(),
        )

    def provider_status(self) -> ActivityProviderStatus:
        try:
            return self.provider.status()
        except Exception as error:
            return ActivityProviderStatus(
                name="unknown",
                display_name="状態不明",
                available=False,
                active=False,
                detail=f"活動取得状態を確認できません: {error}",
            )
