from __future__ import annotations

from dataclasses import dataclass

from miniatured_world.activity.models import ActivityFrame
from miniatured_world.world.simulation import WorldSimulation


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    seed: int
    tendency: str
    traits: tuple[str, ...]
    activity_level: str
    activity_intensity: float
    running: bool
    paused: bool
    world_visible: bool
    muted: bool
    activity_collection_enabled: bool
    world_time: float
    humidity: float
    wind: float
    temperature: float
    materials: dict[str, int]
    grid_materials: dict[str, int]
    plant_count: int
    creature_count: int
    events: tuple[str, ...]
    discoveries: tuple[str, ...]

    @classmethod
    def from_simulation(
        cls,
        simulation: WorldSimulation,
        frame: ActivityFrame,
        *,
        running: bool,
        paused: bool,
        world_visible: bool,
        muted: bool,
        activity_collection_enabled: bool,
    ) -> "WorldSnapshot":
        state = simulation.session.state
        intensity = frame.intensity()
        return cls(
            seed=state.seed,
            tendency=state.tendency_id,
            traits=state.trait_ids,
            activity_level=_activity_level(intensity),
            activity_intensity=round(intensity, 3),
            running=running,
            paused=paused,
            world_visible=world_visible,
            muted=muted,
            activity_collection_enabled=activity_collection_enabled,
            world_time=round(state.environment.world_time, 3),
            humidity=round(state.environment.humidity, 3),
            wind=round(state.environment.wind, 3),
            temperature=round(state.environment.temperature, 3),
            materials=dict(sorted(state.material_counts.items())),
            grid_materials=dict(sorted(simulation.grid.material_counts().items())),
            plant_count=len(state.plants),
            creature_count=len(state.creatures),
            events=tuple(state.events),
            discoveries=tuple(sorted(state.discoveries)),
        )


def _activity_level(intensity: float) -> str:
    if intensity >= 0.72:
        return "intense"
    if intensity >= 0.42:
        return "active"
    if intensity >= 0.12:
        return "calm"
    return "quiet"
