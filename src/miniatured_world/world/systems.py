from __future__ import annotations

from miniatured_world.content import ContentCatalog
from miniatured_world.world.models import Creature, Plant, WorldState
from miniatured_world.world.random_provider import RandomProvider


def update_plants(state: WorldState, catalog: ContentCatalog, growth_delta: float) -> None:
    if not state.plants:
        for plant_id, definition in sorted(catalog.plants.items()):
            if state.consume_materials({str(k): int(v) for k, v in definition["required"].items()}):
                state.plants.append(Plant(id=plant_id))
                state.discoveries.add(f"plant:{plant_id}")
                break

    growth_modifier = 1.0
    for trait_id in state.trait_ids:
        growth_modifier += float(catalog.traits[trait_id].get("modifiers", {}).get("growth", 0.0))

    for plant in state.plants:
        plant.growth = min(1.0, plant.growth + growth_delta * growth_modifier)
        if plant.growth >= 0.66:
            plant.stage = "plant"
        elif plant.growth >= 0.28:
            plant.stage = "germination"


def update_creatures(state: WorldState, catalog: ContentCatalog, random_provider: RandomProvider) -> None:
    if not state.creatures:
        creature_id = sorted(catalog.creatures)[0]
        state.creatures.append(Creature(id=creature_id))

    for creature in state.creatures:
        definition = catalog.creatures[creature.id]
        creature.energy = max(0.0, creature.energy - float(definition.get("energy_decay", 0.04)))
        preferred_food = str(definition.get("preferred_food", "food"))
        if state.material_counts.get(preferred_food, 0) > 0 and creature.energy < 0.85:
            state.material_counts[preferred_food] -= 1
            creature.energy = min(1.0, creature.energy + 0.35)
            creature.state = "eat"
            state.discoveries.add(f"creature:{creature.id}")
        elif state.environment.world_time % 4.0 > 3.2:
            creature.state = "sleep"
        elif random_provider.chance(0.2 + state.environment.wind * 0.15):
            creature.state = "walk"
        else:
            creature.state = "idle"


def update_events(state: WorldState, catalog: ContentCatalog, activity_intensity: float, random_provider: RandomProvider) -> None:
    for event_id, event in sorted(catalog.events.items()):
        condition = event["condition"]
        triggered = False
        if condition == "high_keyboard_and_humidity":
            triggered = activity_intensity > 0.45 and state.environment.humidity > 0.5
        elif condition == "high_idle":
            triggered = state.environment.world_time > 1.0 and activity_intensity < 0.25
        elif condition == "rare_balanced_world":
            balanced = 0.35 < state.environment.humidity < 0.75 and 0.2 < state.environment.wind < 0.7
            triggered = balanced and random_provider.chance(0.04)

        if triggered and event_id not in state.events:
            state.events.append(event_id)
            state.discoveries.add(str(event.get("discovery", event_id)))

