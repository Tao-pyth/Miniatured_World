from __future__ import annotations

from dataclasses import dataclass

from miniatured_world.app.snapshot import WorldSnapshot


@dataclass(frozen=True, slots=True)
class LabScene:
    character_state: str
    cauldron_state: str
    effects: tuple[str, ...]
    material_total: int
    caption: str


def derive_lab_scene(snapshot: WorldSnapshot) -> LabScene:
    """UI向けに、既存World状態を小さなラボの表示状態へ読み替える。"""
    material_total = sum(snapshot.materials.values())
    effects: list[str] = []

    if snapshot.grid_materials or (material_total > 0 and snapshot.activity_intensity >= 0.12):
        effects.append("material_drop")
    if snapshot.activity_intensity >= 0.42 or snapshot.events:
        effects.append("reaction_light")

    if not snapshot.running or snapshot.paused:
        return LabScene("rest", "cauldron_idle", tuple(effects), material_total, "実験を一休みしています")

    if snapshot.discoveries or snapshot.events:
        return LabScene("success", "cauldron_success", tuple(effects), material_total, "新しい反応を記録しました")

    if snapshot.activity_intensity >= 0.85 and material_total == 0:
        effects.append("smoke_puff")
        return LabScene("failure", "cauldron_failure", tuple(effects), material_total, "反応が強すぎるようです")

    if snapshot.activity_level == "quiet":
        return LabScene("rest", "cauldron_idle", tuple(effects), material_total, "静かに観察を続けています")

    if material_total > 0 or snapshot.activity_intensity >= 0.12:
        return LabScene("work", "cauldron_receive", tuple(effects), material_total, "届いた素材を実験中です")

    return LabScene("idle", "cauldron_idle", tuple(effects), material_total, "素材の到着を待っています")
