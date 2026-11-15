from enum import StrEnum


class Classification(StrEnum):
    MEASURED = "measured"
    INFERRED = "inferred"
    HEURISTIC = "heuristic"
    MANUAL = "manual"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisResolution(StrEnum):
    PREVIEW = "preview"
    STANDARD = "standard"
    HIGH = "high"
    NATIVE = "native"
