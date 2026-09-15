"""保存データの検証。例外メッセージにデータの内容を含めない。"""

from dataclasses import fields
import math

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


def validate_discovery(data: dict) -> None:
    validate_record(data, {"schema_version", "discoveries"})
    discoveries = data.get("discoveries", [])
    if not isinstance(discoveries, list) or not all(isinstance(item, str) for item in discoveries):
        raise ValueError("不正な発見データ")
