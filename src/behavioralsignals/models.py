import json
from enum import IntEnum
from typing import List, Literal, Optional
from pathlib import Path
from datetime import date
from datetime import datetime as datetime_aliased

from pydantic import Field, BaseModel, ConfigDict, computed_field, field_validator

from .generated import api_pb2 as pb


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


class StreamingOptions(BaseModel):
    sample_rate: int = Field(16000, gt=0, description="PCM sample rate (Hz).")
    encoding: Literal["LINEAR_PCM"] = Field(..., description="Audio encoding format.")
    level: Literal["segment", "utterance", "all"] = Field(
        "segment",
        description="Level of granularity for the streaming results. "
        "Use 'segment' for segment-level results, 'utterance' for utterance-level results. "
        "Use 'all' for both segment and utterance results.",
    )

    def to_pb_config(self) -> pb.AudioConfig:
        """Convert the level to a protobuf Level enum."""
        level = {
            "segment": pb.Level.segment,
            "utterance": pb.Level.utterance,
            "all": None,
        }[self.level]

        encoding = {"LINEAR_PCM": pb.AudioEncoding.LINEAR_PCM}[self.encoding]
        config = pb.AudioConfig(sample_rate_hertz=self.sample_rate, encoding=encoding)
        if level is not None:
            config.level = level
        return config


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

    pid: int = Field(..., description="Unique ID for the processing job")
    cid: Optional[int] = Field(None, description="Client ID that requested the processing")
    name: Optional[str] = Field(None, description="Label of the processing job (Client defined)")
    status: Optional[int] = Field(
        None,
        description="Shows the processing state of the job. Status is 0: pending, 1: processing, 2: completed, -1:failed, -2 aborted",
    )
    statusmsg: Optional[str] = Field(None, description="Reason for success or failure")
    duration: Optional[float] = Field(None, description="duration of the audio signal (in sec)")
    datetime: Optional[datetime_aliased] = Field(
        None,
        description="date and time the request for processing was inserted into the system",
    )
    meta: Optional[str] = Field(None, description="A JSON string containing additional metadata")

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


class ModelPredictions(BaseModel):
    label: Optional[str] = Field(None, description="The name of the class", example="happy")
    posterior: Optional[str] = Field(
        None, description="The probability of this class being present", example="0.754"
    )
    dominantInSegments: Optional[List[int]] = Field(
        None, description="The segments in which this class is dominant"
    )


class ResultItem(BaseModel):
    id: Optional[str] = Field(None, description="The id of the segment/utterance", example="1")
    startTime: Optional[str] = Field(
        None, description="The start time of the segment/utterance in seconds", example="0.209"
    )
    endTime: Optional[str] = Field(
        None, description="The end time of the segment/utterance in seconds", example="7.681"
    )
    task: Optional[str] = Field(
        None,
        description="The behavioral attribute. Can be one of diarization, deepfake, asr, gender, age, language, features, emotion, strength, positivity, speaking_rate, hesitation, politeness. "
        "Consider visiting the guides in behavioralsignals.readme.io for the latest examples.",
        example="emotion",
    )
    prediction: Optional[List[ModelPredictions]] = None
    finalLabel: Optional[str] = Field(
        None, description="The dominant value of the behavioral attribute", example="happy"
    )
    level: Optional[str] = Field(
        None,
        description="Whether this result corresponds to a segment/utterance",
        example="utterance",
    )
    embedding: Optional[str] = Field(
        None,
        description="The corresponding embedding (present in diarization or features). It's a stringified array of length 728.",
        example="[11.614513397216797, -15.228992462158203, -4.92175817489624, ...]",
    )

    @computed_field
    @property
    def st(self) -> float:
        return float(self.startTime)

    @computed_field
    @property
    def et(self) -> float:
        return float(self.endTime)


class ResultResponse(BaseModel):
    pid: Optional[int] = Field(None, description="Unique ID for the processing job")
    cid: Optional[int] = Field(None, description="Client ID that requested the processing")
    code: Optional[int] = Field(None, description="Code indicating status")
    message: Optional[str] = Field(None, description="Description of status")
    results: Optional[List[ResultItem]] = None


class StreamingResultResponse(BaseModel):
    pid: Optional[int] = Field(None, description="Unique ID for the processing job")
    cid: Optional[int] = Field(None, description="Client ID that requested the processing")
    message_id: Optional[int] = Field(
        None, alias="messageId", description="Incremental message ID for the stream"
    )
    results: Optional[List[ResultItem]] = Field(
        None, alias="result", description="List of result items"
    )
