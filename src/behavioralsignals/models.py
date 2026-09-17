import json
from enum import IntEnum
from typing import Literal
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
    details: dict | None = None


class StreamingOptions(BaseModel):
    sample_rate: int = Field(default=16000, gt=0, description="PCM sample rate (Hz).")
    encoding: Literal["LINEAR_PCM"] = Field(..., description="Audio encoding format.")
    level: Literal["segment", "utterance", "all"] = Field(
        default="segment",
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
    name: str | None = Field(None, description="Optional name for the job request")
    embeddings: bool = Field(
        False, description="Whether to include speaker and behavioral embeddings in the result"
    )
    meta: str | None = Field(
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


class S3UrlUploadParams(BaseModel):
    url: str = Field(..., description="The S3 presigned url containing the audio")
    name: str | None = Field(None, description="Optional name for the job request")
    embeddings: bool = Field(
        False, description="Whether to include speaker and behavioral embeddings in the result"
    )
    meta: str | None = Field(
        None, description="Metadata json containing any extra user-defined metadata"
    )

    @field_validator("meta")
    @classmethod
    def validate_meta_json(cls, v):
        if v is not None:
            try:
                json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("meta must be valid JSON string")
        return v


class DeepfakeAudioUploadParams(AudioUploadParams):
    enable_generator_detection: bool = Field(
        False,
        description="Whether to include prediction for the source of the deepfake (generator model)",
    )


class DeepfakeS3UrlUploadParams(S3UrlUploadParams):
    enable_generator_detection: bool = Field(
        False,
        description="Whether to include prediction for the source of the deepfake (generator model)",
    )


class ProcessItem(BaseModel):
    """Individual process in the list"""

    pid: int = Field(..., description="Unique ID for the processing job")
    cid: int | None = Field(None, description="Client ID that requested the processing")
    name: str | None = Field(None, description="Label of the processing job (Client defined)")
    status: int | None = Field(
        None,
        description="Shows the processing state of the job. Status is 0: pending, 1: processing, 2: completed, -1:failed, -2 aborted",
    )
    statusmsg: str | None = Field(None, description="Reason for success or failure")
    duration: float | None = Field(None, description="duration of the audio signal (in sec)")
    datetime: datetime_aliased | None = Field(
        None,
        description="date and time the request for processing was inserted into the system",
    )
    meta: str | None = Field(None, description="A JSON string containing additional metadata")

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
    start_date: date | None = Field(
        None,
        alias="startDate",
        description="Filter processes created on or after this date (YYYY-MM-DD)",
    )
    end_date: date | None = Field(
        None,
        alias="endDate",
        description="Filter processes created on or before this date (YYYY-MM-DD)",
    )


class ProcessListResponse(BaseModel):
    """Response from list processes endpoint"""

    processes: list[ProcessItem]

    @computed_field
    @property
    def total_count(self) -> int:
        return len(self.processes)

    def completed_processes(self) -> list[ProcessItem]:
        return [p for p in self.processes if p.is_completed]

    def processing_processes(self) -> list[ProcessItem]:
        return [p for p in self.processes if p.is_processing]

    def failed_processes(self) -> list[ProcessItem]:
        return [p for p in self.processes if p.is_failed]


class _SerializableModel(BaseModel):
    """Base for result models that omits null fields on serialization by default."""

    def model_dump(self, **kwargs):
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)

    def model_dump_json(self, **kwargs):
        kwargs.setdefault("exclude_none", True)
        return super().model_dump_json(**kwargs)


class ModelPredictions(_SerializableModel):
    label: str | None = Field(None, description="The name of the class", examples=["happy"])
    posterior: str | None = Field(
        None, description="The probability of this class being present", examples=["0.754"]
    )
    score: str | None = Field(
        None,
        description="The regression score for continuous tasks (e.g. intensity), bounded in (0,1)",
        examples=["0.62"],
    )
    dominantInSegments: list[int] | None = Field(
        None, description="The segments in which this class is dominant"
    )


class ResultItem(_SerializableModel):
    id: str | None = Field(None, description="The id of the segment/utterance", examples=["1"])
    startTime: str | None = Field(
        None, description="The start time of the segment/utterance in seconds", examples=["0.209"]
    )
    endTime: str | None = Field(
        None, description="The end time of the segment/utterance in seconds", examples=["7.681"]
    )
    task: str | None = Field(
        None,
        description="The behavioral attribute. Can be one of diarization, deepfake, visual_deepfake, asr, gender, age, language, features, emotion, strength, positivity, speaking_rate, hesitation, politeness. "
        "Consider visiting the guides in behavioralsignals.readme.io for the latest examples.",
        examples=["emotion"],
    )
    prediction: list[ModelPredictions] | None = None
    finalLabel: str | None = Field(
        None, description="The dominant value of the behavioral attribute", examples=["happy"]
    )
    level: str | None = Field(
        None,
        description="Whether this result corresponds to a segment/utterance",
        examples=["utterance"],
    )
    embedding: str | None = Field(
        None,
        description="The corresponding embedding (present in diarization or features). It's a stringified array of length 728.",
        examples=["[11.614513397216797, -15.228992462158203, -4.92175817489624, ...]"],
    )

    @computed_field
    @property
    def st(self) -> float | None:
        return None if self.startTime is None else float(self.startTime)

    @computed_field
    @property
    def et(self) -> float | None:
        return None if self.endTime is None else float(self.endTime)


class ResultResponse(_SerializableModel):
    pid: int | None = Field(None, description="Unique ID for the processing job")
    cid: int | None = Field(None, description="Client ID that requested the processing")
    code: int | None = Field(None, description="Code indicating status")
    message: str | None = Field(None, description="Description of status")
    results: list[ResultItem] | None = None


class VideoResultResponse(_SerializableModel):
    """Result of a video deepfake detection process.

    Unlike the audio result response, a video process returns two separate result
    lists: one for the deepfake detection performed on the audio track and one for
    the deepfake detection performed on the video frames.
    """

    pid: int | None = Field(None, description="Unique ID for the processing job")
    cid: int | None = Field(None, description="Client ID that requested the processing")
    code: int | None = Field(None, description="Code indicating status")
    message: str | None = Field(None, description="Description of status")
    audio_results: list[ResultItem] | None = Field(
        None, description="Audio deepfake detection results"
    )
    video_results: list[ResultItem] | None = Field(
        None, description="Video deepfake detection results"
    )


class StreamingResultResponse(_SerializableModel):
    pid: int | None = Field(None, description="Unique ID for the processing job")
    cid: int | None = Field(None, description="Client ID that requested the processing")
    message_id: int | None = Field(
        None, alias="messageId", description="Incremental message ID for the stream"
    )
    results: list[ResultItem] | None = Field(
        None, alias="result", description="List of result items"
    )
