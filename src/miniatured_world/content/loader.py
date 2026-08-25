from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any


@dataclass(frozen=True, slots=True)
class ContentCatalog:
    schema_version: int
    materials: dict[str, dict[str, Any]]
    tendencies: dict[str, dict[str, Any]]
    traits: dict[str, dict[str, Any]]
    plants: dict[str, dict[str, Any]]
    creatures: dict[str, dict[str, Any]]
    events: dict[str, dict[str, Any]]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ContentCatalog":
        return cls(
            schema_version=int(data["schema_version"]),
            materials=_by_id(data["materials"]),
            tendencies=_by_id(data["tendencies"]),
            traits=_by_id(data["traits"]),
            plants=_by_id(data["plants"]),
            creatures=_by_id(data["creatures"]),
            events=_by_id(data["events"]),
        )

    def validate(self) -> None:
        if self.schema_version < 1:
            raise ValueError("content schema_version must be positive")
        for section_name in ("materials", "tendencies", "traits", "plants", "creatures", "events"):
            section = getattr(self, section_name)
            if not section:
                raise ValueError(f"content section is empty: {section_name}")


def load_default_catalog() -> ContentCatalog:
    content_path = resources.files("miniatured_world.content").joinpath("defaults.json")
    data = json.loads(content_path.read_text(encoding="utf-8"))
    catalog = ContentCatalog.from_mapping(data)
    catalog.validate()
    return catalog


def _by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = item["id"]
        if item_id in result:
            raise ValueError(f"duplicate content id: {item_id}")
        result[item_id] = item
    return result

