from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from miniatured_world.activity import ActivityFrame, ActivityProvider, NullActivityProvider
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


@dataclass(slots=True)
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
        return cls(
            service=MiniaturedWorldService.start(seed=seed, data_root=data_root),
            provider=provider or NullActivityProvider(),
        )

    def pause(self) -> None:
        self.state.paused = True

    def resume(self) -> None:
        self.state.paused = False

    def stop(self) -> None:
        self.state.running = False

    def set_activity_collection(self, enabled: bool) -> None:
        self.state.activity_collection_enabled = enabled

    def show_world(self) -> None:
        self.state.world_visible = True

    def hide_world(self) -> None:
        self.state.world_visible = False

    def mute(self) -> None:
        self.state.muted = True

    def unmute(self) -> None:
        self.state.muted = False

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
            self.state.muted = not self.state.muted
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
        )
