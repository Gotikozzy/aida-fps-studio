from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from dg_fps.core.enums import Classification
from dg_fps.core.roi import RectangleROI


def _validate_confidence(value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError("Confidence must be between 0.0 and 1.0")


@dataclass(frozen=True, slots=True)
class TimeRange:
    start_time: float
    end_time: float
    start_frame: int | None = None
    end_frame: int | None = None

    def __post_init__(self) -> None:
        if self.start_time < 0 or self.end_time < self.start_time:
            raise ValueError("Invalid time range")
        if self.start_frame is not None and self.start_frame < 0:
            raise ValueError("Start frame cannot be negative")
        if self.end_frame is not None and self.start_frame is None:
            raise ValueError("End frame requires a start frame")
        if (
            self.start_frame is not None
            and self.end_frame is not None
            and self.end_frame < self.start_frame
        ):
            raise ValueError("End frame cannot precede start frame")


@dataclass(frozen=True, slots=True)
class Observation:
    metric: str
    value: float | int | str | bool
    unit: str | None = None

    def __post_init__(self) -> None:
        if not self.metric.strip():
            raise ValueError("Observation metric cannot be empty")


@dataclass(frozen=True, slots=True)
class Interpretation:
    statement: str
    confidence: float

    def __post_init__(self) -> None:
        if not self.statement.strip():
            raise ValueError("Interpretation statement cannot be empty")
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class AnalyzerIdentity:
    id: str
    version: str


@dataclass(frozen=True, slots=True)
class Finding:
    analyzer: AnalyzerIdentity
    category: str
    type: str
    classification: Classification
    range: TimeRange
    confidence: float
    observations: tuple[Observation, ...] = ()
    interpretations: tuple[Interpretation, ...] = ()
    limitations: tuple[str, ...] = ()
    audience_explanation: str | None = None
    region: RectangleROI | None = None
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence)
        if not self.category.strip() or not self.type.strip():
            raise ValueError("Finding category and type cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["classification"] = self.classification.value
        if self.region is not None:
            data["region"] = self.region.to_dict()
        return data
