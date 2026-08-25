from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Environment:
    humidity: float = 0.45
    wind: float = 0.1
    temperature: float = 0.5
    world_time: float = 0.0

    def clamp(self) -> None:
        self.humidity = _clamp(self.humidity)
        self.wind = _clamp(self.wind)
        self.temperature = _clamp(self.temperature)
        self.world_time = max(0.0, self.world_time)


@dataclass(slots=True)
class Plant:
    id: str
    stage: str = "seed"
    growth: float = 0.0


@dataclass(slots=True)
class Creature:
    id: str
    state: str = "idle"
    energy: float = 1.0


@dataclass(slots=True)
class WorldState:
    seed: int
    tendency_id: str
    trait_ids: tuple[str, ...]
    environment: Environment = field(default_factory=Environment)
    material_counts: dict[str, int] = field(default_factory=dict)
    plants: list[Plant] = field(default_factory=list)
    creatures: list[Creature] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    discoveries: set[str] = field(default_factory=set)

    def add_material(self, material_id: str, amount: int = 1) -> None:
        self.material_counts[material_id] = self.material_counts.get(material_id, 0) + max(0, amount)

    def consume_materials(self, required: dict[str, int]) -> bool:
        if any(self.material_counts.get(material_id, 0) < amount for material_id, amount in required.items()):
            return False
        for material_id, amount in required.items():
            self.material_counts[material_id] -= amount
        return True

    def summary(self) -> dict[str, object]:
        return {
            "seed": self.seed,
            "tendency": self.tendency_id,
            "traits": list(self.trait_ids),
            "environment": {
                "humidity": round(self.environment.humidity, 3),
                "wind": round(self.environment.wind, 3),
                "temperature": round(self.environment.temperature, 3),
                "world_time": round(self.environment.world_time, 3),
            },
            "materials": dict(sorted(self.material_counts.items())),
            "plants": [(plant.id, plant.stage, round(plant.growth, 3)) for plant in self.plants],
            "creatures": [(creature.id, creature.state, round(creature.energy, 3)) for creature in self.creatures],
            "events": list(self.events),
            "discoveries": sorted(self.discoveries),
        }


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))

