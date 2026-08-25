from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from miniatured_world.persistence.settings import (
    ActivitySettings,
    DataSettings,
    DisplaySettings,
    GeneralSettings,
    NotificationSettings,
    PerformanceSettings,
    PrivacySettings,
    Settings,
    SoundSettings,
)


@dataclass(frozen=True, slots=True)
class DiscoveryRecord:
    schema_version: int = 1
    discoveries: list[str] = field(default_factory=list)


class JsonStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def save_settings(self, settings: Settings) -> Path:
        return self._atomic_write("settings.json", asdict(settings))

    def load_settings(self) -> Settings:
        data = self._read("settings.json")
        if not data:
            return Settings()
        return Settings(
            schema_version=int(data.get("schema_version", 1)),
            general=GeneralSettings(**data.get("general", {})),
            display=DisplaySettings(**data.get("display", {})),
            activity=ActivitySettings(**data.get("activity", {})),
            sound=SoundSettings(**data.get("sound", {})),
            notifications=NotificationSettings(**data.get("notifications", {})),
            privacy=PrivacySettings(**data.get("privacy", {})),
            performance=PerformanceSettings(**data.get("performance", {})),
            data=DataSettings(**data.get("data", {})),
        )

    def save_discovery(self, record: DiscoveryRecord) -> Path:
        safe_discoveries = sorted(set(record.discoveries))
        return self._atomic_write(
            "discovery.json",
            {"schema_version": record.schema_version, "discoveries": safe_discoveries},
        )

    def load_discovery(self) -> DiscoveryRecord:
        data = self._read("discovery.json")
        if not data:
            return DiscoveryRecord()
        return DiscoveryRecord(
            schema_version=int(data.get("schema_version", 1)),
            discoveries=list(data.get("discoveries", [])),
        )

    def _read(self, name: str) -> dict[str, Any]:
        path = self._root / name
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _atomic_write(self, name: str, data: dict[str, Any]) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        target = self._root / name
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=self._root,
            prefix=f".{name}.",
            suffix=".tmp",
        ) as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            temp_name = handle.name
        os.replace(temp_name, target)
        return target
