"""明示出力された診断ログの所有記録。内容やActivity列は一覧へ保存しない。"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

from miniatured_world.persistence.store import JsonStore
from miniatured_world.persistence.validation import json_object, reject_constant


@dataclass(frozen=True, slots=True)
class LogEntry:
    path: str
    sha256: str


def identify_log(path: Path) -> LogEntry:
    if path.is_symlink():
        raise ValueError("リンクは削除対象にできません。")
    canonical = path.resolve()
    with canonical.open("rb") as handle:
        first = handle.readline(8193)
    if not first.endswith(b"\n") or len(first) > 8192:
        raise ValueError("ログの形式を確認できません。")
    try:
        header = json.loads(first, object_pairs_hook=json_object, parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        raise ValueError("ログの形式を確認できません。") from None
    if not isinstance(header, dict) or header.get("event") != "start" or not {"duration_seconds", "tick_interval_ms", "realtime", "provider", "process", "utc_time", "elapsed_seconds"} <= header.keys():
        raise ValueError("ログの形式を確認できません。")
    if not isinstance(header["provider"], dict) or not isinstance(header["process"], dict):
        raise ValueError("ログの形式を確認できません。")
    if header.get("application", "miniatured-world") != "miniatured-world" or header.get("log_schema_version", 1) != 1:
        raise ValueError("未対応のログです。")
    if not {"name", "available", "active"} <= header["provider"].keys() or "pid" not in header["process"]:
        raise ValueError("ログの形式を確認できません。")
    for key in ("duration_seconds", "tick_interval_ms", "elapsed_seconds"):
        value = header[key]
        if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)) or value < 0:
            raise ValueError("ログの形式を確認できません。")
    if type(header["realtime"]) is not bool:
        raise ValueError("ログの形式を確認できません。")
    return LogEntry(str(canonical), hashlib.sha256(first).hexdigest())


class LogRegistry:
    def __init__(self, store: JsonStore | None) -> None:
        self.store = store
        self._entries = {item["path"]: LogEntry(**item) for item in store.load_log_index()} if store else {}
        self._closers: dict[str, Callable[[], None]] = {}
        self.registration_failed = False

    @property
    def entries(self) -> tuple[LogEntry, ...]:
        return tuple(self._entries[key] for key in sorted(self._entries))

    @property
    def protected(self) -> bool:
        return bool(self.store and self.store.is_read_protected("log-index.json"))

    def register(self, path: Path, closer: Callable[[], None]) -> None:
        if self.store is None:
            return
        try:
            entry = identify_log(path)
            if len(self._entries) >= 4096 and entry.path not in self._entries:
                raise ValueError("管理できるログ数の上限です。")
            self._entries[entry.path] = entry
            self._closers[entry.path] = closer
            self._persist()
        except (OSError, ValueError, UnicodeError):
            self.registration_failed = True

    def _persist(self) -> bool:
        if self.store is None:
            return True
        if self.protected:
            return False
        if not self._entries:
            return self.store.delete_data("log-index.json")
        self.store.resume_saving("log-index.json")
        try:
            return self.store.save_log_index([asdict(entry) for entry in self.entries]) is not None
        except ValueError:
            self.registration_failed = True
            return False

    def delete(self, entries: Iterable[LogEntry]) -> dict[str, bool]:
        if self.store is None:
            return {}
        result = {}
        for entry in entries:
            path = Path(entry.path)
            try:
                closer = self._closers.pop(entry.path, None)
                if closer is not None:
                    closer()
                if not path.is_absolute() or path.is_symlink() or str(path.resolve()) != entry.path:
                    raise ValueError("ログの保存先が変わっています。")
                if path.exists() and identify_log(path) != entry:
                    raise ValueError("ログの内容が変わっています。")
                path.unlink(missing_ok=True)
            except (OSError, ValueError, UnicodeError):
                # 明示選択した旧ログも、失敗した場合は次の操作のために保持する。
                self._entries.setdefault(entry.path, entry)
                result[entry.path] = False
            else:
                self._entries.pop(entry.path, None)
                result[entry.path] = True
        result["log-index.json"] = self._persist()
        return result
