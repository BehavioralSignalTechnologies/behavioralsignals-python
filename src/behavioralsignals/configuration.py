from typing import Union, Optional
from dataclasses import dataclass


TimeoutType = Union[float, tuple[float, float]]

@dataclass
class Configuration:
    user_id: str
    api_key: str
    api_url: str = "https://api.behavioralsignals.com/v5"
    streaming_api_url: str = "streaming.behavioralsignals.com:443"
    timeout: Optional[TimeoutType] = None
    use_ssl: bool = False