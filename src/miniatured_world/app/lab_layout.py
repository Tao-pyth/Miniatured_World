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
    pixel_scale: int = 2
    character_home: tuple[float, float] = (694, 696)

    @property
    def gimmicks(self) -> tuple[GimmickPlacement, ...]:
        return (
            GimmickPlacement("cauldron", (510, 730), (96 * self.pixel_scale, 112 * self.pixel_scale), (630, 690)),
            GimmickPlacement("book", (848, 692), (48 * self.pixel_scale, 68 * self.pixel_scale), (770, 686)),
            GimmickPlacement("basket", (660, 766), (52 * self.pixel_scale, 28 * self.pixel_scale), (714, 744)),
            GimmickPlacement("product", (788, 758), (48 * self.pixel_scale, 16 * self.pixel_scale), (734, 726)),
        )

    def gimmick(self, key: str) -> GimmickPlacement:
        return next(item for item in self.gimmicks if item.key == key)


# 全前景に同じ整数倍率を適用する。
DEFAULT_LAYOUT = LabLayout()
