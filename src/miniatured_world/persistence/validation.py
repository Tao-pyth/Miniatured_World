"""保存データの検証。例外メッセージにデータの内容を含めない。"""

from dataclasses import fields
import math
import re
from pathlib import Path

from miniatured_world.persistence.settings import Settings


class UnsupportedData(ValueError):
    pass


def json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("重複した項目")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("非有限の数値")


def validate_record(data, allowed_fields: set[str]) -> None:
    if not isinstance(data, dict):
        raise ValueError("不正なデータ構造")
    if data.keys() - allowed_fields:
        raise UnsupportedData("未対応の項目")
    version = data.get("schema_version", 1)
    if type(version) is not int or version != 1:
        raise UnsupportedData("未対応のスキーマ")


def validate_settings(data: dict) -> None:
    defaults = Settings()
    validate_record(data, {item.name for item in fields(defaults)})
    if "activity_notice" in data and not isinstance(data["activity_notice"], str):
        raise ValueError("不正な説明状態")
    for item in fields(defaults):
        if item.name in ("schema_version", "activity_notice") or item.name not in data:
            continue
        section = data[item.name]
        if not isinstance(section, dict):
            raise ValueError("不正な設定構造")
        expected = getattr(defaults, item.name)
        if section.keys() - {field.name for field in fields(expected)}:
            raise UnsupportedData("未対応の設定項目")
        if item.name == "window":
            validate_window(section)
            continue
        for name, value in section.items():
            default = getattr(expected, name)
            if type(default) is float:
                if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1_000_000:
                    raise ValueError("不正な数値設定")
                if name in ("opacity", "master_volume", "ambience_volume", "event_volume") and value > 1:
                    raise ValueError("不正な割合")
            elif type(value) is not type(default):
                raise ValueError("不正な設定型")
            elif type(default) is int and not 1 <= value <= 2_147_483_647:
                raise ValueError("不正な整数設定")
            if item.name == "privacy" and value is not False:
                raise ValueError("許可されていないプライバシー設定")


def validate_window(section: dict) -> None:
    from miniatured_world.persistence.settings import WindowSettings

    window = WindowSettings(**section)
    if type(window.saved) is not bool:
        raise ValueError("不正なウィンドウ設定")
    if any(type(value) is not int for value in (window.x, window.y, window.width, window.height)):
        raise ValueError("不正なウィンドウ設定")
    if not all(-1_000_000 <= value <= 1_000_000 for value in (window.x, window.y)):
        raise ValueError("不正なウィンドウ位置")
    if window.saved:
        if not all(1 <= value <= 100_000 for value in (window.width, window.height)):
            raise ValueError("不正なウィンドウ寸法")
    elif window != WindowSettings():
        raise ValueError("不正な未保存ウィンドウ設定")


def validate_discovery(data: dict) -> None:
    validate_record(data, {"schema_version", "discoveries"})
    discoveries = data.get("discoveries", [])
    if not isinstance(discoveries, list) or not all(isinstance(item, str) for item in discoveries):
        raise ValueError("不正な発見データ")


def validate_log_index(data: dict) -> None:
    validate_record(data, {"schema_version", "logs"})
    entries = data.get("logs", [])
    if not isinstance(entries, list) or len(entries) > 4096:
        raise ValueError("不正なログ一覧")
    seen = set()
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ValueError("不正なログ項目")
        path, identity = item["path"], item["sha256"]
        if not isinstance(path, str) or not path or "\0" in path or not Path(path).is_absolute() or path in seen:
            raise ValueError("不正なログ保存先")
        if not isinstance(identity, str) or re.fullmatch(r"[0-9a-f]{64}", identity) is None:
            raise ValueError("不正なログ識別値")
        seen.add(path)
