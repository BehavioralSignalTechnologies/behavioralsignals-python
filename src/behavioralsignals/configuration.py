from pydantic import field_validator
from pydantic.dataclasses import dataclass


TimeoutType = float | tuple[float, float]
DEFAULT_TIMEOUT: TimeoutType = (10.0, 60.0)  # (connect, read) seconds per HTTP request
DEFAULT_UPLOAD_TIMEOUT: TimeoutType = (10.0, 300.0)  # (connect, read) seconds per upload request


@dataclass
class Configuration:
    cid: str
    api_key: str
    api_url: str = "https://api.behavioralsignals.com/v5"
    streaming_api_url: str = "streaming.behavioralsignals.com:443"
    timeout: TimeoutType | None = DEFAULT_TIMEOUT
    upload_timeout: TimeoutType | None = DEFAULT_UPLOAD_TIMEOUT
    use_ssl: bool = True

    @field_validator("cid", mode="before")
    @classmethod
    def convert_cid(cls, v):
        if not isinstance(v, (str, int)):
            raise TypeError(f"cid must be str or int, got {type(v).__name__}")
        return str(v)
