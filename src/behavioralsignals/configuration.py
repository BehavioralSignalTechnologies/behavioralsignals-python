from typing import Union, Optional

from pydantic import field_validator
from pydantic.dataclasses import dataclass


TimeoutType = Union[float, tuple[float, float]]


@dataclass
class Configuration:
    cid: Union[str, int]
    api_key: str
    api_url: str = "https://api.behavioralsignals.com/v5"
    streaming_api_url: str = "streaming.behavioralsignals.com:443"
    timeout: Optional[TimeoutType] = None
    use_ssl: bool = True

    @field_validator("cid", mode="before")
    @classmethod
    def convert_cid(cls, v):
        if not isinstance(v, (str, int)):
            raise TypeError(f"cid must be str or int, got {type(v).__name__}")
        return str(v)
