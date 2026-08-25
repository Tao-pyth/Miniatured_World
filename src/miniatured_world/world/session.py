from __future__ import annotations

from dataclasses import dataclass

from miniatured_world.content import ContentCatalog, load_default_catalog
from miniatured_world.world.models import Creature, Environment, WorldState
from miniatured_world.world.random_provider import RandomProvider


@dataclass(slots=True)
class WorldSession:
    state: WorldState
    random: RandomProvider
    catalog: ContentCatalog

    @classmethod
    def create(cls, seed: int, catalog: ContentCatalog | None = None) -> "WorldSession":
        content = catalog or load_default_catalog()
        random_provider = RandomProvider(seed)
        tendency_id = random_provider.choice(tuple(content.tendencies))
        trait_ids = tuple(random_provider.sample(tuple(content.traits), 2))
        environment = Environment()

        tendency = content.tendencies[tendency_id]
        for key, delta in tendency.get("environment", {}).items():
            setattr(environment, key, getattr(environment, key) + float(delta))
        for trait_id in trait_ids:
            for key, delta in content.traits[trait_id].get("modifiers", {}).items():
                if hasattr(environment, key):
                    setattr(environment, key, getattr(environment, key) + float(delta))
        environment.clamp()

        state = WorldState(
            seed=seed,
            tendency_id=tendency_id,
            trait_ids=trait_ids,
            environment=environment,
        )
        creature_id = sorted(content.creatures)[0]
        state.creatures.append(Creature(creature_id))
        return cls(state=state, random=random_provider, catalog=content)
