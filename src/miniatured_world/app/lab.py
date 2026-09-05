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


def derive_lab_scene(snapshot: WorldSnapshot, *, reaction: bool = False) -> LabScene:
    """UI向けに、既存World状態を小さなラボの表示状態へ読み替える。"""
    material_total = sum(snapshot.materials.values())
    effects: list[str] = []

    if not snapshot.running or snapshot.paused:
        return LabScene("rest", "cauldron_idle", (), material_total, "実験を一休みしています")

    if material_total > 0 and snapshot.activity_collection_enabled and snapshot.activity_intensity >= 0.12:
        effects.append("material_drop")
    if snapshot.activity_intensity >= 0.42 or reaction:
        effects.append("reaction_light")

    if reaction:
        return LabScene("success", "cauldron_success", tuple(effects), material_total, "新しい反応を記録しました")

    if snapshot.activity_intensity >= 0.85 and material_total == 0:
        effects.append("smoke_puff")
        return LabScene("failure", "cauldron_failure", tuple(effects), material_total, "反応が強すぎるようです")

    if snapshot.activity_level == "quiet":
        return LabScene("rest", "cauldron_idle", tuple(effects), material_total, "静かに観察を続けています")

    if material_total > 0 or snapshot.activity_intensity >= 0.12:
        return LabScene("work", "cauldron_receive", tuple(effects), material_total, "届いた素材を実験中です")

    return LabScene("idle", "cauldron_idle", tuple(effects), material_total, "素材の到着を待っています")


class LabAnimation:
    """Transient view state; never advances simulation or retains raw activity."""

    def __init__(self) -> None:
        self.elapsed_ms = 0
        self._snapshot: WorldSnapshot | None = None
        self._reaction_until = 0

    def observe(self, snapshot: WorldSnapshot) -> None:
        previous = self._snapshot
        if previous is None or snapshot.seed != previous.seed or snapshot.world_time < previous.world_time:
            self.elapsed_ms = 0
            self._reaction_until = 0
        elif snapshot.running and not snapshot.paused:
            new_event = set(snapshot.events) - set(previous.events)
            new_discovery = set(snapshot.discoveries) - set(previous.discoveries)
            if new_event or new_discovery:
                self._reaction_until = self.elapsed_ms + 3200
        self._snapshot = snapshot

    def advance(self, elapsed_ms: int) -> None:
        snapshot = self._snapshot
        if snapshot is not None and snapshot.running and not snapshot.paused and snapshot.world_visible:
            self.elapsed_ms += max(0, elapsed_ms)

    @property
    def frame_index(self) -> int:
        return self.elapsed_ms // 125 % 8

    @property
    def scene(self) -> LabScene | None:
        if self._snapshot is None:
            return None
        return derive_lab_scene(self._snapshot, reaction=self.elapsed_ms < self._reaction_until)
