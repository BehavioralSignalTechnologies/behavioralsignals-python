from importlib.metadata import PackageNotFoundError, version

from .base import StreamingResults, BehavioralSignalsError
from .client import Client
from .models import END_OF_TURN, EndOfTurn, StreamingOptions, VideoResultResponse
from .deepfakes import Deepfakes
from .behavioral import Behavioral


try:
    __version__ = version("behavioralsignals")
except PackageNotFoundError:  # running from source without installing
    __version__ = "unknown"

__all__ = [
    "END_OF_TURN",
    "Behavioral",
    "BehavioralSignalsError",
    "Client",
    "Deepfakes",
    "EndOfTurn",
    "StreamingOptions",
    "StreamingResults",
    "VideoResultResponse",
]
