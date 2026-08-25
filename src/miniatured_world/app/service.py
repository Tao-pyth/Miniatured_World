from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from miniatured_world.activity import ActivityAggregator, PrivacyFilter
from miniatured_world.persistence import DiscoveryManager, JsonStore, Settings
from miniatured_world.world import WorldSession, WorldSimulation


@dataclass(slots=True)
class MiniaturedWorldService:
    simulation: WorldSimulation
    aggregator: ActivityAggregator = field(default_factory=ActivityAggregator)
    privacy_filter: PrivacyFilter = field(default_factory=PrivacyFilter)
    settings: Settings = field(default_factory=Settings)
    store: JsonStore | None = None
    discovery_manager: DiscoveryManager = field(default_factory=DiscoveryManager)
    now_ms: int = 0

    @classmethod
    def start(cls, seed: int, data_root: Path | None = None) -> "MiniaturedWorldService":
        store = JsonStore(data_root) if data_root else None
        settings = store.load_settings() if store else Settings()
        discovery_manager = DiscoveryManager.load(store)
        session = WorldSession.create(seed)
        return cls(
            simulation=WorldSimulation(session),
            settings=settings,
            store=store,
            discovery_manager=discovery_manager,
        )

    def inject_demo_activity(self, frame_index: int) -> None:
        base = self.now_ms
        for offset, key in enumerate(("a", "b", "1", " ", "Enter")):
            self.aggregator.add(self.privacy_filter.keyboard(key, base + offset * 30))
        self.aggregator.add(self.privacy_filter.pointer_move(120 + frame_index * 5, 40, base + 180))
        if frame_index % 2 == 0:
            self.aggregator.add(self.privacy_filter.pointer_click(base + 220))
        if frame_index % 3 == 0:
            self.aggregator.add(self.privacy_filter.idle(base + 300, 10_000))

    def step(self, elapsed_ms: int = 1000):
        self.now_ms += elapsed_ms
        frame = self.aggregator.frame(self.now_ms)
        self.simulation.step(frame)
        if self.store:
            self.store.save_settings(self.settings)
        self.discovery_manager.merge(self.simulation.session.state.discoveries)
        return frame

    def summary_text(self) -> str:
        summary = self.simulation.summary()
        return (
            f"Miniatured World seed={summary['seed']} "
            f"tendency={summary['tendency']} "
            f"discoveries={len(summary['discoveries'])} "
            f"events={len(summary['events'])}"
        )
