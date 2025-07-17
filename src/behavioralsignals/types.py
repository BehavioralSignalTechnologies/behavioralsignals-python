from enum import IntEnum
from typing import Any, List, Literal, Optional
from datetime import datetime

from pydantic import Field, BaseModel, computed_field

from .generated import api_pb2 as pb


class StreamingOptions(BaseModel):
    sample_rate: int = Field(16000, gt=0, description="PCM sample rate (Hz).")
    level: Literal["segment", "utterance", "all"] = Field(
        "segment",
        description="Level of granularity for the streaming results. "
        "Use 'segment' for segment-level results, 'utterance' for utterance-level results."
        " Use 'all' for both segment and utterance results.",
    )

    def to_pb_config(self) -> pb.AudioConfig:
        """Convert the level to a protobuf Level enum."""
        level = {
            "segment": pb.Level.segment,
            "utterance": pb.Level.utterance,
            "all": None,
        }[self.level]

        config = pb.AudioConfig(sample_rate_hertz=self.sample_rate)
        if level is not None:
            config.level = level
        return config


class ProcessStatus(IntEnum):
    """Status codes for process states"""

    PENDING = 0
    PROCESSING = 1
    COMPLETED = 2
    FAILED = -1
    INSUFFICIENT_CREDITS = -2


class APIError(BaseModel):
    code: int
    message: str
    details: Optional[dict] = None


class ProcessItem(BaseModel):
    """Individual process in the list"""

    pid: int
    cid: int
    name: str
    status: int
    statusmsg: str
    duration: float
    datetime: datetime
    meta: Optional[dict] = None

    @property
    def is_completed(self) -> bool:
        return self.status == ProcessStatus.COMPLETED

    @property
    def is_processing(self) -> bool:
        return self.status == ProcessStatus.PROCESSING

    @property
    def is_failed(self) -> bool:
        return self.status == ProcessStatus.FAILED

    @property
    def is_pending(self) -> bool:
        return self.status == ProcessStatus.PENDING


class ProcessListResponse(BaseModel):
    """Response from list processes endpoint"""

    processes: List[ProcessItem]

    @computed_field
    @property
    def total_count(self) -> int:
        return len(self.processes)

    def completed_processes(self) -> List[ProcessItem]:
        return [p for p in self.processes if p.is_completed]

    def processing_processes(self) -> List[ProcessItem]:
        return [p for p in self.processes if p.is_processing]

    def failed_processes(self) -> List[ProcessItem]:
        return [p for p in self.processes if p.is_failed]


class Prediction(BaseModel):
    label: Optional[str] = None
    posterior: Optional[str] = None
    dominantInSegments: List[Any] = Field(default_factory=list, deprecated=True)


class ResultItem(BaseModel):
    id: str
    startTime: str
    endTime: str
    task: str
    prediction: List[Prediction]
    finalLabel: Optional[str] = None
    level: str
    embedding: Optional[str] = None

    @computed_field
    @property
    def st(self) -> float:
        return float(self.startTime)

    @computed_field
    @property
    def et(self) -> float:
        return float(self.endTime)

    @computed_field
    @property
    def duration(self) -> float:
        return self.et - self.st


class ResultResponse(BaseModel):
    pid: int
    cid: int
    code: int
    message: str
    results: List[ResultItem]
