from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AudioEncoding(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    LINEAR_PCM: _ClassVar[AudioEncoding]

class Level(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    segment: _ClassVar[Level]
    utterance: _ClassVar[Level]
LINEAR_PCM: AudioEncoding
segment: Level
utterance: Level

class AudioConfig(_message.Message):
    __slots__ = ("encoding", "sample_rate_hertz", "level", "logits", "feature_embedding")
    ENCODING_FIELD_NUMBER: _ClassVar[int]
    SAMPLE_RATE_HERTZ_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    LOGITS_FIELD_NUMBER: _ClassVar[int]
    FEATURE_EMBEDDING_FIELD_NUMBER: _ClassVar[int]
    encoding: AudioEncoding
    sample_rate_hertz: int
    level: Level
    logits: bool
    feature_embedding: bool
    def __init__(self, encoding: _Optional[_Union[AudioEncoding, str]] = ..., sample_rate_hertz: _Optional[int] = ..., level: _Optional[_Union[Level, str]] = ..., logits: bool = ..., feature_embedding: bool = ...) -> None: ...

class AudioStream(_message.Message):
    __slots__ = ("cid", "x_auth_token", "config", "audio_content")
    CID_FIELD_NUMBER: _ClassVar[int]
    X_AUTH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    AUDIO_CONTENT_FIELD_NUMBER: _ClassVar[int]
    cid: int
    x_auth_token: str
    config: AudioConfig
    audio_content: bytes
    def __init__(self, cid: _Optional[int] = ..., x_auth_token: _Optional[str] = ..., config: _Optional[_Union[AudioConfig, _Mapping]] = ..., audio_content: _Optional[bytes] = ...) -> None: ...

class Prediction(_message.Message):
    __slots__ = ("label", "posterior", "logit")
    LABEL_FIELD_NUMBER: _ClassVar[int]
    POSTERIOR_FIELD_NUMBER: _ClassVar[int]
    LOGIT_FIELD_NUMBER: _ClassVar[int]
    label: str
    posterior: str
    logit: str
    def __init__(self, label: _Optional[str] = ..., posterior: _Optional[str] = ..., logit: _Optional[str] = ...) -> None: ...

class InferenceResult(_message.Message):
    __slots__ = ("id", "start_time", "end_time", "task", "prediction", "final_label", "embedding", "level")
    ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    TASK_FIELD_NUMBER: _ClassVar[int]
    PREDICTION_FIELD_NUMBER: _ClassVar[int]
    FINAL_LABEL_FIELD_NUMBER: _ClassVar[int]
    EMBEDDING_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    id: str
    start_time: str
    end_time: str
    task: str
    prediction: _containers.RepeatedCompositeFieldContainer[Prediction]
    final_label: str
    embedding: str
    level: Level
    def __init__(self, id: _Optional[str] = ..., start_time: _Optional[str] = ..., end_time: _Optional[str] = ..., task: _Optional[str] = ..., prediction: _Optional[_Iterable[_Union[Prediction, _Mapping]]] = ..., final_label: _Optional[str] = ..., embedding: _Optional[str] = ..., level: _Optional[_Union[Level, str]] = ...) -> None: ...

class StreamResult(_message.Message):
    __slots__ = ("cid", "pid", "message_id", "result")
    CID_FIELD_NUMBER: _ClassVar[int]
    PID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    cid: int
    pid: int
    message_id: int
    result: _containers.RepeatedCompositeFieldContainer[InferenceResult]
    def __init__(self, cid: _Optional[int] = ..., pid: _Optional[int] = ..., message_id: _Optional[int] = ..., result: _Optional[_Iterable[_Union[InferenceResult, _Mapping]]] = ...) -> None: ...
