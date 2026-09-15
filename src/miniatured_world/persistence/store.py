from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from miniatured_world.persistence.validation import (
    UnsupportedData, json_object, reject_constant, validate_discovery, validate_settings,
)
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


@dataclass(frozen=True, slots=True)
class StorageIssue:
    name: str
    reason: str

    @property
    def message(self) -> str:
        label = "設定" if self.name == "settings.json" else "発見データ"
        cause = "このバージョンでは扱えないため" if self.reason == "unsupported" else "読み込めないため"
        return (
            f"{label}を{cause}、元ファイルを保護しています。"
            f"今回の{label}の変更は保存されません。"
            "修復・復元後、アプリを再起動すると再確認します。"
        )


class JsonStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._issues: dict[str, StorageIssue] = {}
        self._checked: set[str] = set()

    @property
    def issues(self) -> tuple[StorageIssue, ...]:
        return tuple(self._issues.values())

    @property
    def root(self) -> Path:
        return self._root

    def save_settings(self, settings: Settings) -> Path | None:
        if "settings.json" not in self._checked:
            self.load_settings()
        return self._atomic_write("settings.json", asdict(settings))

    def load_settings(self) -> Settings:
        data = self._read("settings.json", validate_settings)
        if "settings.json" in self._issues:
            defaults = Settings()
            return replace(defaults, activity=replace(defaults.activity, enabled=False))
        if not data:
            return Settings()
        notice = data.get("activity_notice", "legacy")
        if notice not in ("unseen", "legacy", "shown"):
            notice = "unseen"
        return Settings(
            schema_version=int(data.get("schema_version", 1)),
            activity_notice=notice,
            general=GeneralSettings(**data.get("general", {})),
            display=DisplaySettings(**data.get("display", {})),
            activity=ActivitySettings(**data.get("activity", {})),
            sound=SoundSettings(**data.get("sound", {})),
            notifications=NotificationSettings(**data.get("notifications", {})),
            privacy=PrivacySettings(**data.get("privacy", {})),
            performance=PerformanceSettings(**data.get("performance", {})),
            data=DataSettings(**data.get("data", {})),
        )

    def save_discovery(self, record: DiscoveryRecord) -> Path | None:
        if "discovery.json" not in self._checked:
            self.load_discovery()
        safe_discoveries = sorted(set(record.discoveries))
        return self._atomic_write(
            "discovery.json",
            {"schema_version": record.schema_version, "discoveries": safe_discoveries},
        )

    def load_discovery(self) -> DiscoveryRecord:
        data = self._read("discovery.json", validate_discovery)
        if not data:
            return DiscoveryRecord()
        return DiscoveryRecord(
            schema_version=int(data.get("schema_version", 1)),
            discoveries=list(data.get("discoveries", [])),
        )

    def _read(self, name: str, validate) -> dict[str, Any]:
        # 一度保護したファイルを、同じセッションの初期値で上書きしない。
        if name in self._issues:
            return {}
        path = self._root / name
        self._checked.add(name)
        try:
            data = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=json_object, parse_constant=reject_constant,
            )
            validate(data)
            return data
        except FileNotFoundError:
            return {}
        except UnsupportedData:
            reason = "unsupported"
        except (OSError, UnicodeError, ValueError, TypeError, OverflowError, RecursionError):
            reason = "unreadable"
        self._issues[name] = StorageIssue(name, reason)
        return {}

    def _atomic_write(self, name: str, data: dict[str, Any]) -> Path | None:
        if name in self._issues:
            return None
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
