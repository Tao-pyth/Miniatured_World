from __future__ import annotations

from dataclasses import dataclass, replace
import math

from miniatured_world.app.snapshot import WorldSnapshot
from miniatured_world.app.lab_layout import DEFAULT_LAYOUT, GimmickPlacement, LabLayout
from miniatured_world.app.hand_motion import ObjectOwnership, TransferEvent, handling_state, motion_clip


@dataclass(frozen=True, slots=True)
class GimmickState:
    placement: GimmickPlacement
    state: str


WALK_SPEED = 80.0  # 舞台ピクセル/秒。画面の拡縮率には依存しない。
WALK_STRIDE = 48.0  # 左右の足が一巡する移動距離。
WALK_FRAMES = 8
WORK_KEYS = {"arrive": None, "read": "book", "collect": "basket", "mix": "cauldron", "place": "product", "return": None}


def workflow_for(layout: LabLayout) -> tuple[tuple[str, int], ...]:
    previous = layout.character_home
    result = []
    for phase, key in WORK_KEYS.items():
        target = layout.character_home if key is None else layout.gimmick(key).work_position
        travel_ms = math.ceil(math.dist(previous, target) / WALK_SPEED * 1000)
        action_ms = 1500 if phase == "arrive" else 100 if phase == "return" else motion_clip(phase).duration_ms
        result.append((phase, travel_ms + action_ms))
        previous = target
    return tuple(result)


WORKFLOW = workflow_for(DEFAULT_LAYOUT)
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
    action_progress: float = 0.0
    walk_frame: int | None = None
    gimmicks: tuple[GimmickState, ...] = ()
    character_position: tuple[float, float] = DEFAULT_LAYOUT.character_home
    facing_right: bool = False
    batch_materials: tuple[str, ...] = ()
    product_visible: bool = False
    action_frame: int | None = None
    action_elapsed_ms: float = 0
    cycle_id: int = 0
    objects: tuple[ObjectOwnership, ...] = ()
    vessel_location: str = "none"
    vessel_contents: str = "empty"
    vessel_angle: float = 0
    tray_product_id: int | None = None
    transfers: tuple[TransferEvent, ...] = ()


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
    """表示だけを進める時計。受け渡し時刻も描画も同じ経過時間から決まる。"""

    def __init__(self, layout: LabLayout = DEFAULT_LAYOUT) -> None:
        self.layout = layout
        self.workflow = workflow_for(layout)
        self.cycle_ms = sum(duration for _, duration in self.workflow)
        self.elapsed_ms = 0
        self._snapshot: WorldSnapshot | None = None
        self._reaction_until = 0
        self._cycle_start: int | None = None
        self._cycle_id = 0
        self._pending_materials: tuple[str, ...] = ()
        self._batch_materials: tuple[str, ...] = ()
        self._tray_cycle_id: int | None = None
        self._recorded_transfers: set[str] = set()
        self._transfers: list[TransferEvent] = []

    def phase_start_ms(self, phase: str) -> int:
        start = 0
        for name, duration in self.workflow:
            if name == phase:
                return start
            start += duration
        raise ValueError(phase)

    def action_start_ms(self, phase: str) -> int:
        duration = dict(self.workflow)[phase]
        return self.phase_start_ms(phase) + duration - motion_clip(phase).duration_ms

    def transfer_schedule(self) -> tuple[tuple[str, int], ...]:
        return tuple(
            (kind, self.action_start_ms(phase) + motion_clip(phase).event_time(event))
            for kind, phase, event in (
                ("collect", "collect", "grab"),
                ("pour", "mix", "pour_end"),
                ("recover", "mix", "recover"),
                ("place", "place", "release"),
            )
        )

    def _start_cycle(self, start_ms: int, materials: tuple[str, ...]) -> None:
        self._cycle_start = start_ms
        self._cycle_id += 1
        self._batch_materials = materials
        self._recorded_transfers.clear()

    def observe(self, snapshot: WorldSnapshot) -> None:
        previous = self._snapshot
        if previous is None or snapshot.seed != previous.seed or snapshot.world_time < previous.world_time:
            self.elapsed_ms = 0
            self._reaction_until = 0
            self._cycle_start = None
            self._cycle_id = 0
            self._pending_materials = ()
            self._batch_materials = ()
            self._tray_cycle_id = None
            self._recorded_transfers.clear()
            self._transfers.clear()
        elif snapshot.running and not snapshot.paused:
            if set(snapshot.events) - set(previous.events) or set(snapshot.discoveries) - set(previous.discoveries):
                self._reaction_until = self.elapsed_ms + 3200
            arrived = tuple(sorted(key for key, value in snapshot.materials.items() if value > previous.materials.get(key, 0)))[:6]
            if arrived and snapshot.activity_collection_enabled:
                if self._cycle_start is None:
                    self._start_cycle(self.elapsed_ms, arrived)
                else:
                    self._pending_materials = tuple(sorted(set(self._pending_materials) | set(arrived)))[:6]
        self._snapshot = snapshot

    def advance(self, elapsed_ms: int) -> None:
        snapshot = self._snapshot
        if snapshot is None or not snapshot.running or snapshot.paused or not snapshot.world_visible:
            return
        self.elapsed_ms += max(0, elapsed_ms)
        while self._cycle_start is not None:
            end = self._cycle_start + self.cycle_ms
            reached = min(self.elapsed_ms, end)
            for kind, offset in self.transfer_schedule():
                when = self._cycle_start + offset
                if when <= reached and kind not in self._recorded_transfers:
                    self._recorded_transfers.add(kind)
                    self._transfers.append(TransferEvent(self._cycle_id, kind, when))
                    self._transfers = self._transfers[-16:]
                    if kind == "place":
                        self._tray_cycle_id = self._cycle_id
            if self.elapsed_ms < end:
                break
            self._cycle_start = None
            if self._pending_materials:
                # 通知を受けた時刻へずらさず、前巡の終端から余り時間を進める。
                materials, self._pending_materials = self._pending_materials, ()
                self._start_cycle(end, materials)

    @property
    def frame_index(self) -> int:
        return self.elapsed_ms // 125 % 8

    @property
    def scene(self) -> LabScene | None:
        if self._snapshot is None:
            return None
        base = derive_lab_scene(self._snapshot, reaction=self.elapsed_ms < self._reaction_until)
        phase, progress, action_progress, action_elapsed = "idle", 0.0, 0.0, 0.0
        walk_frame = action_frame = None
        states = {"book": "open", "basket": "empty", "cauldron": base.cauldron_state, "product": "ready" if self._tray_cycle_id else "empty"}
        position = self.layout.character_home
        facing_right = False
        if self._cycle_start is not None:
            elapsed = self.elapsed_ms - self._cycle_start
            previous_position = self.layout.character_home
            for name, duration in self.workflow:
                key = WORK_KEYS[name]
                target = self.layout.character_home if key is None else self.layout.gimmick(key).work_position
                if elapsed < duration:
                    phase, progress = name, elapsed / duration
                    distance = math.dist(previous_position, target)
                    travel_ms = math.ceil(distance / WALK_SPEED * 1000)
                    travelled = min(distance, elapsed / 1000 * WALK_SPEED)
                    blend = travelled / distance if distance else 1.0
                    position = tuple(a + (b - a) * blend for a, b in zip(previous_position, target))
                    if elapsed < travel_ms:
                        walk_frame = int(travelled / WALK_STRIDE * WALK_FRAMES) % WALK_FRAMES
                        facing_right = target[0] > previous_position[0]
                    else:
                        action_elapsed = elapsed - travel_ms
                        action_progress = min(1.0, action_elapsed / max(1, duration - travel_ms))
                        if name in {"read", "collect", "mix", "place"}:
                            action_frame = motion_clip(name).frame_at(action_elapsed)
                        facing_right = name in {"read", "place"}
                    break
                elapsed -= duration
                previous_position = target

            walking = walk_frame is not None
            states["basket"] = "arriving" if phase == "arrive" else "taking" if phase == "collect" and not walking else "full" if phase in {"read", "collect"} else "empty"
            states["book"] = "turning" if phase == "read" and not walking else "open"
            states["product"] = "placing" if phase == "place" and not walking else states["product"]
            states["cauldron"] = "cauldron_idle"
            if phase == "mix" and action_frame is not None and action_frame >= motion_clip("mix").event_frame("pour_start"):
                states["cauldron"] = "cauldron_success" if action_frame >= motion_clip("mix").event_frame("recover") else "cauldron_receive"
            elif phase == "place" and not walking:
                states["cauldron"] = "cauldron_success"
            if walking:
                destinations = {"read": "本", "collect": "素材かご", "mix": "釜", "place": "トレー", "return": "待機位置"}
                base = replace(base, character_state="walk", cauldron_state=states["cauldron"], effects=(), caption=f"{destinations[phase]}へ歩いています")
            else:
                captions = {"arrive": "素材かごに新しい素材が届きました", "read": "本をめくって手順を確認しています", "collect": "かごから素材を取り出しています", "mix": "素材を釜で調合しています", "place": "完成した小瓶をトレーへ置いています", "return": "次の素材を待っています"}
                effects = ("reaction_light",) if states["cauldron"] in {"cauldron_receive", "cauldron_success"} else ()
                # 一時停止中も同じ原画・所有状態を返す。時計はadvanceで凍結する。
                base = replace(base, character_state="work" if phase == "mix" else "idle", cauldron_state=states["cauldron"], effects=effects, caption=captions[phase])

        handling = handling_state(phase, action_frame, self._cycle_id)
        return replace(
            base, workflow_phase=phase, phase_progress=progress, action_progress=action_progress,
            walk_frame=walk_frame, action_frame=action_frame, action_elapsed_ms=action_elapsed,
            gimmicks=tuple(GimmickState(item, states[item.key]) for item in self.layout.gimmicks),
            character_position=position, facing_right=facing_right, batch_materials=self._batch_materials,
            product_visible=self._tray_cycle_id is not None, cycle_id=self._cycle_id,
            objects=handling.objects, vessel_location=handling.vessel_location,
            vessel_contents=handling.contents, vessel_angle=handling.angle,
            tray_product_id=self._tray_cycle_id, transfers=tuple(self._transfers),
        )
