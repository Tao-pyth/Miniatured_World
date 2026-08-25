from __future__ import annotations

from dataclasses import dataclass, field

from miniatured_world.persistence.store import DiscoveryRecord, JsonStore


@dataclass(slots=True)
class DiscoveryManager:
    store: JsonStore | None = None
    discoveries: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, store: JsonStore | None = None) -> "DiscoveryManager":
        manager = cls(store=store)
        if store:
            manager.discoveries.update(store.load_discovery().discoveries)
        return manager

    def merge(self, discovered: set[str] | list[str] | tuple[str, ...]) -> DiscoveryRecord:
        self.discoveries.update(str(item) for item in discovered)
        record = DiscoveryRecord(discoveries=sorted(self.discoveries))
        if self.store:
            self.store.save_discovery(record)
        return record

