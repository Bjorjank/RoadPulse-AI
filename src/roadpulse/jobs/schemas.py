from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Status(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Point(BaseModel):
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)


class StartRequest(BaseModel):
    line: tuple[Point, Point]
    trails: bool = True

    @model_validator(mode="after")
    def distinct(self):
        if self.line[0] == self.line[1]:
            raise ValueError("Choose two distinct counting-line points")
        return self


class Health(BaseModel):
    status: Literal["ok"] = "ok"


class System(BaseModel):
    model: str
    model_ready: bool
    available_providers: list[str]
    profile: str
    worker_limit: int = 1


class Metrics(BaseModel):
    initialization_seconds: float
    inference_average_ms: float
    inference_median_ms: float
    inference_p95_ms: float
    model_only_fps: float
    processing_fps: float
    elapsed_seconds: float
    frame_processing_seconds: float
    output_writing_seconds: float
    peak_ram_bytes: int
    os: str
    cpu: str
    gpu: str | None = None


class Results(BaseModel):
    job_id: str
    model: str
    provider: str
    provider_warnings: list[str]
    frames_processed: int
    reported_frames: int | None = None
    decode_warnings: list[str] = Field(default_factory=list)
    tracked_observations: int
    total: int
    counts: dict[str, int]
    directions: dict[str, int]
    volume: list[dict[str, int | float]]
    metrics: Metrics


class Job(BaseModel):
    id: str
    filename: str
    status: Status
    width: int
    height: int
    fps: float
    total_frames: int
    provider: str | None = None
    processed_frames: int = 0
    progress: float = 0
    error: str | None = None
    line: list[list[float]] | None = None
    results: Results | None = None
