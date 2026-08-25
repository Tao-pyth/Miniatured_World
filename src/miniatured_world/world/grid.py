from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GridSimulation:
    width: int = 24
    height: int = 16
    cells: list[list[str | None]] = field(init=False)

    def __post_init__(self) -> None:
        self.cells = [[None for _ in range(self.width)] for _ in range(self.height)]

    def spawn(self, material_id: str, column: int) -> bool:
        x = column % self.width
        if self.cells[0][x] is not None:
            return False
        self.cells[0][x] = material_id
        return True

    def step(self, wind_bias: float = 0.0) -> None:
        direction = 1 if wind_bias >= 0 else -1
        for y in range(self.height - 2, -1, -1):
            for x in range(self.width):
                material = self.cells[y][x]
                if material is None:
                    continue
                if self._move(y, x, y + 1, x):
                    continue
                if self._move(y, x, y + 1, x + direction):
                    continue
                self._move(y, x, y + 1, x - direction)

    def material_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.cells:
            for material in row:
                if material is not None:
                    counts[material] = counts.get(material, 0) + 1
        return counts

    def _move(self, source_y: int, source_x: int, target_y: int, target_x: int) -> bool:
        if target_y < 0 or target_y >= self.height or target_x < 0 or target_x >= self.width:
            return False
        if self.cells[target_y][target_x] is not None:
            return False
        self.cells[target_y][target_x] = self.cells[source_y][source_x]
        self.cells[source_y][source_x] = None
        return True

