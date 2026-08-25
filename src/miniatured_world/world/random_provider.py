from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class RandomProvider:
    seed: int
    _random: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._random = random.Random(self.seed)

    def choice(self, items: Sequence[T]) -> T:
        return self._random.choice(list(items))

    def sample(self, items: Sequence[T], count: int) -> list[T]:
        return self._random.sample(list(items), min(count, len(items)))

    def weighted_choice(self, weights: Mapping[str, float]) -> str:
        total = sum(max(0.0, weight) for weight in weights.values())
        if total <= 0:
            return sorted(weights)[0]
        mark = self._random.uniform(0.0, total)
        cumulative = 0.0
        for key in sorted(weights):
            cumulative += max(0.0, weights[key])
            if cumulative >= mark:
                return key
        return sorted(weights)[-1]

    def chance(self, probability: float) -> bool:
        return self._random.random() < max(0.0, min(1.0, probability))
