from __future__ import annotations

from dataclasses import dataclass, field

from miniatured_world.activity.models import ActivityFrame
from miniatured_world.world.grid import GridSimulation
from miniatured_world.world.interpreter import WorldInterpreter
from miniatured_world.world.session import WorldSession
from miniatured_world.world.systems import update_creatures, update_events, update_plants


@dataclass(slots=True)
class WorldSimulation:
    session: WorldSession
    grid: GridSimulation = field(default_factory=GridSimulation)
    _interpreter: WorldInterpreter = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._interpreter = WorldInterpreter(self.session.catalog)

    def step(self, frame: ActivityFrame) -> None:
        state = self.session.state
        effect = self._interpreter.interpret(state.tendency_id, frame, self.session.random)

        for index, material_id in enumerate(effect.materials):
            state.add_material(material_id)
            self.grid.spawn(material_id, state.seed + index + int(state.environment.world_time * 10))

        state.environment.wind += effect.wind_delta
        state.environment.world_time += effect.time_delta
        state.environment.clamp()

        self.grid.step(wind_bias=state.environment.wind - 0.5)
        update_plants(state, self.session.catalog, effect.growth_delta)
        update_creatures(state, self.session.catalog, self.session.random)
        update_events(state, self.session.catalog, frame.intensity(), self.session.random)

    def summary(self) -> dict[str, object]:
        summary = self.session.state.summary()
        summary["grid_materials"] = self.grid.material_counts()
        return summary
