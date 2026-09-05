"""共通舞台の道具配置。座標は入力イベントではなく描画上の位置。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GimmickPlacement:
    key: str
    position: tuple[float, float]
    size: tuple[float, float]
    work_position: tuple[float, float]


@dataclass(frozen=True, slots=True)
class LabLayout:
    character_scale: float = 1.0
    cauldron_scale: float = 1.0
    character_home: tuple[float, float] = (694, 696)

    @property
    def gimmicks(self) -> tuple[GimmickPlacement, ...]:
        return (
            GimmickPlacement("cauldron", (510, 730), (192 * self.cauldron_scale, 256 * self.cauldron_scale), (672, 684)),
            GimmickPlacement("book", (900, 692), (98, 140), (724, 696)),
            GimmickPlacement("basket", (660, 766), (104, 54), (750, 726)),
            GimmickPlacement("product", (847, 758), (96, 30), (744, 706)),
        )

    def gimmick(self, key: str) -> GimmickPlacement:
        return next(item for item in self.gimmicks if item.key == key)


# 3案の静止比較後、釜を手前へ30px置き、手元と口の高さを合わせた。
DEFAULT_LAYOUT = LabLayout(character_scale=1.4, cauldron_scale=1.3)
