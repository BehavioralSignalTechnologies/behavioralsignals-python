from importlib.metadata import PackageNotFoundError, version

from .base import BehavioralSignalsError
from .client import Client
from .models import StreamingOptions, VideoResultResponse
from .deepfakes import Deepfakes
from .behavioral import Behavioral


try:
    __version__ = version("behavioralsignals")
except PackageNotFoundError:  # running from source without installing
    __version__ = "unknown"

__all__ = [
    "Behavioral",
    "BehavioralSignalsError",
    "Client",
    "Deepfakes",
    "StreamingOptions",
    "VideoResultResponse",
]
