from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from dg_fps.media.timestamp_index import TimestampIndex

ResultT = TypeVar("ResultT")


def _no_op() -> None:
    return None


def _no_progress(progress: int, message: str) -> None:
    del progress, message


@dataclass(frozen=True, slots=True)
class AnalysisRequirements:
    needs_video_decode: bool = True
    needs_gpu: bool = False
    needs_timestamp_index: bool = True


@dataclass(frozen=True, slots=True)
class AnalysisFrameRange:
    start_frame: int
    end_frame: int
    label: str

    def __post_init__(self) -> None:
        if self.start_frame < 0 or self.end_frame < self.start_frame:
            raise ValueError("Invalid analysis frame range")
        if not self.label.strip():
            raise ValueError("Analysis range label cannot be empty")

    @property
    def frame_count(self) -> int:
        return self.end_frame - self.start_frame + 1


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    source_path: Path
    container_fps: float
    check_cancelled: Callable[[], None] = field(default=_no_op, repr=False)
    report_progress: Callable[[int, str], None] = field(default=_no_progress, repr=False)
    frame_ranges: tuple[AnalysisFrameRange, ...] = ()
    timestamp_index: TimestampIndex | None = None


class Analyzer[ResultT](ABC):
    analyzer_id: str
    analyzer_version: str

    @abstractmethod
    def requirements(self) -> AnalysisRequirements:
        raise NotImplementedError

    @abstractmethod
    def analyze(self, context: AnalysisContext) -> ResultT:
        raise NotImplementedError
