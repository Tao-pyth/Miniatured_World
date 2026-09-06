"""原画の時間・接点・所有状態。Worldや実際の入力とは独立した表示用データ。"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
import json


@dataclass(frozen=True, slots=True)
class MotionFrame:
    sprite: str
    hand_mask: str
    grip: tuple[int, int]
    duration_ms: int
    vessel_angle: float = 0


@dataclass(frozen=True, slots=True)
class MotionClip:
    frames: tuple[MotionFrame, ...]
    events: tuple[tuple[str, int], ...]

    @property
    def duration_ms(self) -> int:
        return sum(frame.duration_ms for frame in self.frames)

    def frame_start(self, index: int) -> int:
        return sum(frame.duration_ms for frame in self.frames[:index])

    def event_frame(self, name: str) -> int:
        return dict(self.events)[name]

    def event_time(self, name: str) -> int:
        return self.frame_start(self.event_frame(name))

    def frame_at(self, elapsed_ms: float) -> int:
        ends = tuple(self.frame_start(index + 1) for index in range(len(self.frames)))
        return min(len(self.frames) - 1, bisect_right(ends, max(0, elapsed_ms)))


@lru_cache(maxsize=1)
def motion_data() -> dict:
    path = resources.files("miniatured_world") / "assets" / "hand_motion.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["schema"] != 1 or data["native_size"] != [128, 128] or data["baseline"] != 120:
        raise ValueError("手元原画の形式が一致しません")
    return data


@lru_cache(maxsize=4)
def motion_clip(action: str) -> MotionClip:
    data = motion_data()["series"][action]
    frames = tuple(
        MotionFrame(
            frame["sprite"], frame["hand_mask"], tuple(frame["grip"]),
            frame["duration_ms"], frame["vessel_angle"],
        )
        for frame in data["frames"]
    )
    clip = MotionClip(frames, tuple(data["events"].items()))
    if not frames or any(frame.duration_ms <= 0 for frame in frames) or clip.duration_ms != data["duration_ms"]:
        raise ValueError(f"手元原画の時間が不正です: {action}")
    if any(not 0 <= index < len(frames) for _, index in clip.events):
        raise ValueError(f"手元原画の接触位置が不正です: {action}")
    return clip


@dataclass(frozen=True, slots=True)
class ObjectOwnership:
    object_id: str
    owner: str
    physical_vessel_id: str | None = None


@dataclass(frozen=True, slots=True)
class TransferEvent:
    cycle_id: int
    kind: str
    elapsed_ms: int


@dataclass(frozen=True, slots=True)
class HandlingState:
    objects: tuple[ObjectOwnership, ...] = ()
    vessel_location: str = "none"
    contents: str = "empty"
    angle: float = 0


def handling_state(phase: str, frame_index: int | None, cycle_id: int) -> HandlingState:
    """同じ物理容器の役割を調合容器から完成品へ一度だけ切り替える。"""
    if not cycle_id:
        return HandlingState()
    index = -1 if frame_index is None else frame_index
    collected = phase in {"mix", "place", "return", "idle"} or (
        phase == "collect" and index >= motion_clip("collect").event_frame("grab")
    )
    poured = phase in {"place", "return", "idle"} or (
        phase == "mix" and index >= motion_clip("mix").event_frame("pour_end")
    )
    recovered = phase in {"place", "return", "idle"} or (
        phase == "mix" and index >= motion_clip("mix").event_frame("recover")
    )
    placed = phase in {"return", "idle"} or (
        phase == "place" and index >= motion_clip("place").event_frame("release")
    )
    vessel_id = f"vessel:{cycle_id}"
    objects = (
        ObjectOwnership(f"materials:{cycle_id}", "cauldron" if poured else "hand" if collected else "basket"),
        ObjectOwnership(f"mixing_vial:{cycle_id}", "converted" if recovered else "hand" if collected else "basket", None if recovered else vessel_id),
        ObjectOwnership(f"product_vial:{cycle_id}", "tray" if placed else "hand" if recovered else "cauldron", vessel_id if recovered else None),
    )
    angle = motion_clip("mix").frames[index].vessel_angle if phase == "mix" and index >= 0 else 0
    return HandlingState(
        objects,
        "tray" if placed else "hand" if collected else "basket",
        "product" if recovered else "empty" if poured else "materials",
        angle,
    )
