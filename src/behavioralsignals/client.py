from functools import cached_property

from .base import BaseClient
from .deepfakes import Deepfakes
from .behavioral import Behavioral


class Client(BaseClient):
    @cached_property
    def behavioral(self) -> Behavioral:
        """Client for the Behavioral API."""
        return Behavioral(**self._sub_client_args())

    @cached_property
    def deepfakes(self) -> Deepfakes:
        """Client for the Deepfakes API."""
        return Deepfakes(**self._sub_client_args())

    def _sub_client_args(self) -> dict:
        return {
            "cid": self.config.cid,
            "api_key": self.config.api_key,
            "timeout": self.config.timeout,
            "upload_timeout": self.config.upload_timeout,
        }
