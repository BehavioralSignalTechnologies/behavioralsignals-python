import json
from enum import IntEnum
from typing import Any, List, Literal, Optional
from pathlib import Path
from datetime import date, datetime

from pydantic import Field, BaseModel, ConfigDict, computed_field, field_validator

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


class AudioUploadParams(BaseModel):
    file_path: str = Field(..., description="Path to the audio file to upload")
    name: Optional[str] = Field(None, description="Optional name for the job request")
    embeddings: bool = Field(
        False, description="Whether to include speaker and behavioral embeddings in the result"
    )
    meta: Optional[str] = Field(
        None, description="Metadata json containing any extra user-defined metadata"
    )

    # Optional: Add validation for file path
    @field_validator("file_path")
    @classmethod
    def validate_file_exists(cls, v):
        if not Path(v).exists():
            raise ValueError(f"File does not exist: {v}")
        return v

    @field_validator("meta")
    @classmethod
    def validate_meta_json(cls, v):
        if v is not None:
            try:
                json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("meta must be valid JSON string")
        return v


class ProcessItem(BaseModel):
    """Individual process in the list"""

    pid: int
    cid: int
    name: str
    status: int
    statusmsg: str
    duration: float
    datetime: datetime
    meta: Optional[str] = Field(
        None, description="Metadata json containing any extra user-defined metadata"
    )

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


class ProcessListParams(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    page: int = Field(0, ge=0, description="Page number for pagination.")
    page_size: int = Field(
        1000, ge=1, le=1000, description="Number of processes per page.", alias="pageSize"
    )
    sort: Literal["asc", "desc"] = "asc"
    start_date: Optional[date] = Field(
        None,
        alias="startDate",
        description="Filter processes created on or after this date (YYYY-MM-DD)",
    )
    end_date: Optional[date] = Field(
        None,
        alias="endDate",
        description="Filter processes created on or before this date (YYYY-MM-DD)",
    )


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
