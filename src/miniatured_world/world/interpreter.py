from __future__ import annotations

from dataclasses import dataclass

from miniatured_world.activity.models import ActivityFrame
from miniatured_world.content import ContentCatalog
from miniatured_world.world.random_provider import RandomProvider


@dataclass(frozen=True, slots=True)
class WorldEffect:
    materials: list[str]
    wind_delta: float
    time_delta: float
    growth_delta: float


class WorldInterpreter:
    def __init__(self, catalog: ContentCatalog) -> None:
        self._catalog = catalog

    def interpret(self, tendency_id: str, frame: ActivityFrame, random_provider: RandomProvider) -> WorldEffect:
        tendency = self._catalog.tendencies[tendency_id]
        weights = dict(tendency.get("material_weights", {}))
        material_amount = int(round(frame.keyboard_activity * 5 + frame.burstiness * 2))
        materials = [random_provider.weighted_choice(weights) for _ in range(max(0, material_amount))]
        wind_delta = frame.pointer_activity * 0.08 + frame.scroll_activity * 0.03
        time_delta = 0.1 + frame.idle_ratio * 0.7 + frame.session_duration * 0.002
        growth_delta = frame.idle_ratio * 0.18 + frame.continuity * 0.04
        return WorldEffect(
            materials=materials,
            wind_delta=wind_delta,
            time_delta=time_delta,
            growth_delta=growth_delta,
        )

