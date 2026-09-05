from __future__ import annotations

from dataclasses import dataclass, replace

from miniatured_world.app.snapshot import WorldSnapshot
from miniatured_world.app.lab_layout import DEFAULT_LAYOUT, GimmickPlacement, LabLayout


@dataclass(frozen=True, slots=True)
class GimmickState:
    placement: GimmickPlacement
    state: str


WORKFLOW = (("arrive", 1500), ("read", 2200), ("collect", 1600), ("mix", 3200), ("place", 1800), ("return", 700))
CYCLE_MS = sum(duration for _, duration in WORKFLOW)


def material_transfer_progress(phase: str, progress: float, index: int, count: int) -> float:
    """各素材の移動時刻を共有し、かご内と移動中の二重描画を防ぐ。"""
    if phase == "arrive":
        start, duration = index / max(1, count) * 0.35, 0.65
    elif phase == "collect":
        start, duration = 0.28 + index / max(1, count) * 0.22, 0.42
    else:
        raise ValueError(f"素材移動のない段階です: {phase}")
    return min(1.0, max(0.0, (progress - start) / duration))


@dataclass(frozen=True, slots=True)
class LabScene:
    character_state: str
    cauldron_state: str
    effects: tuple[str, ...]
    material_total: int
    caption: str
    workflow_phase: str = "idle"
    phase_progress: float = 0.0
    gimmicks: tuple[GimmickState, ...] = ()
    character_position: tuple[float, float] = DEFAULT_LAYOUT.character_home
    facing_right: bool = False
    batch_materials: tuple[str, ...] = ()
    product_visible: bool = False


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

    def __init__(self, layout: LabLayout = DEFAULT_LAYOUT) -> None:
        self.layout = layout
        self.elapsed_ms = 0
        self._snapshot: WorldSnapshot | None = None
        self._reaction_until = 0
        self._cycle_start: int | None = None
        self._pending_materials: tuple[str, ...] = ()
        self._batch_materials: tuple[str, ...] = ()
        self._product_visible = False

    def observe(self, snapshot: WorldSnapshot) -> None:
        previous = self._snapshot
        if previous is None or snapshot.seed != previous.seed or snapshot.world_time < previous.world_time:
            self.elapsed_ms = 0
            self._reaction_until = 0
            self._cycle_start = None
            self._pending_materials = ()
            self._batch_materials = ()
            self._product_visible = False
        elif snapshot.running and not snapshot.paused:
            new_event = set(snapshot.events) - set(previous.events)
            new_discovery = set(snapshot.discoveries) - set(previous.discoveries)
            if new_event or new_discovery:
                self._reaction_until = self.elapsed_ms + 3200
            arrived = tuple(sorted(key for key, value in snapshot.materials.items() if value > previous.materials.get(key, 0)))[:6]
            if arrived and snapshot.activity_collection_enabled:
                if self._cycle_start is None:
                    self._cycle_start = self.elapsed_ms
                    self._batch_materials = arrived
                else:
                    # 高頻度の活動通知でも先頭へ戻さず、次回分を最大1回にまとめる。
                    self._pending_materials = tuple(sorted(set(self._pending_materials) | set(arrived)))[:6]
        self._snapshot = snapshot

    def advance(self, elapsed_ms: int) -> None:
        snapshot = self._snapshot
        if snapshot is not None and snapshot.running and not snapshot.paused and snapshot.world_visible:
            self.elapsed_ms += max(0, elapsed_ms)
            if self._cycle_start is not None and self.elapsed_ms - self._cycle_start >= CYCLE_MS - 700:
                self._product_visible = True
            if self._cycle_start is not None and self.elapsed_ms - self._cycle_start >= CYCLE_MS:
                self._product_visible = True
                self._cycle_start = None
                if self._pending_materials:
                    self._cycle_start = self.elapsed_ms
                    self._batch_materials = self._pending_materials
                    self._pending_materials = ()

    @property
    def frame_index(self) -> int:
        return self.elapsed_ms // 125 % 8

    @property
    def scene(self) -> LabScene | None:
        if self._snapshot is None:
            return None
        base = derive_lab_scene(self._snapshot, reaction=self.elapsed_ms < self._reaction_until)
        phase, progress = "idle", 0.0
        states = {"book": "open", "basket": "empty", "cauldron": base.cauldron_state, "product": "ready" if self._product_visible else "empty"}
        position = self.layout.character_home
        facing_right = False
        if self._cycle_start is not None and self._snapshot.running:
            elapsed = self.elapsed_ms - self._cycle_start
            previous_position = self.layout.character_home
            work_keys = {"arrive": None, "read": "book", "collect": "basket", "mix": "cauldron", "place": "product", "return": None}
            for name, duration in WORKFLOW:
                target_key = work_keys[name]
                target = self.layout.character_home if target_key is None else self.layout.gimmick(target_key).work_position
                if elapsed < duration:
                    phase, progress = name, elapsed / duration
                    # 最初の0.45秒で近接する作業位置へ移る。瞬間移動を避ける。
                    blend = min(1.0, elapsed / 450)
                    blend = blend * blend * (3 - 2 * blend)
                    position = tuple(a + (b - a) * blend for a, b in zip(previous_position, target))
                    break
                elapsed -= duration
                previous_position = target
            captions = {"arrive": "素材かごに新しい素材が届きました", "read": "本をめくって手順を確認しています", "collect": "かごから素材を取り出しています", "mix": "素材を釜で調合しています", "place": "完成した小瓶をトレーへ置いています", "return": "次の素材を待っています"}
            states["basket"] = "arriving" if phase == "arrive" else "taking" if phase == "collect" else "full" if phase == "read" else "empty"
            states["book"] = "turning" if phase == "read" else "open"
            states["product"] = "placing" if phase == "place" else states["product"]
            states["cauldron"] = "cauldron_receive" if phase in {"collect", "mix"} else "cauldron_success" if phase == "place" else "cauldron_idle"
            facing_right = phase in {"read", "place"}
            if not self._snapshot.paused:
                base = replace(base, character_state="success" if phase == "place" else "work" if phase == "mix" else "idle", cauldron_state=states["cauldron"], effects=("reaction_light",) if phase in {"mix", "place"} else (), caption=captions[phase])
            else:
                states["cauldron"] = base.cauldron_state
        return replace(base, workflow_phase=phase, phase_progress=progress, gimmicks=tuple(GimmickState(item, states[item.key]) for item in self.layout.gimmicks), character_position=position, facing_right=facing_right, batch_materials=self._batch_materials, product_visible=self._product_visible)
