from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RectangleROI:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0:
            raise ValueError("ROI coordinates cannot be negative")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("ROI dimensions must be positive")

    @property
    def area(self) -> int:
        return self.width * self.height

    def to_dict(self) -> dict[str, Any]:
        return {"type": "rectangle", **asdict(self)}
