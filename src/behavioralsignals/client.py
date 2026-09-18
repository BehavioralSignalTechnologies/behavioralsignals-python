from functools import cached_property
from contextlib import ExitStack

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

    def close(self):
        """Close the session, and the sessions of the sub-clients that were used."""
        with ExitStack() as stack:
            # Callbacks run in reverse, so this session closes last, even if a sub-client fails.
            stack.callback(super().close)
            for name in ("behavioral", "deepfakes"):
                sub_client = self.__dict__.get(name)
                if sub_client is not None:
                    stack.callback(sub_client.close)

    def _sub_client_args(self) -> dict:
        return {
            "cid": self.config.cid,
            "api_key": self.config.api_key,
            "timeout": self.config.timeout,
            "upload_timeout": self.config.upload_timeout,
        }
