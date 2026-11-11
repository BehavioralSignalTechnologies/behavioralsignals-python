from functools import cached_property
from contextlib import ExitStack

from .base import BaseClient
from .deepfakes import Deepfakes
from .behavioral import Behavioral
from .configuration import Configuration


class Client(BaseClient):
    @cached_property
    def behavioral(self) -> Behavioral:
        """Client for the Behavioral API."""
        return Behavioral._with_checked_credentials(self._sub_client_config())

    @cached_property
    def deepfakes(self) -> Deepfakes:
        """Client for the Deepfakes API."""
        return Deepfakes._with_checked_credentials(self._sub_client_config())

    def close(self):
        """Close the session, and the sessions of the sub-clients that were used."""
        with ExitStack() as stack:
            # ExitStack runs every callback, even if one raises.
            # Registering this session first means it closes last.
            stack.callback(super().close)
            for name in ("behavioral", "deepfakes"):
                sub_client = self.__dict__.get(name)
                if sub_client is not None:
                    stack.callback(sub_client.close)

    def _sub_client_config(self) -> Configuration:
        return Configuration(
            cid=self.config.cid,
            api_key=self.config.api_key,
            timeout=self.config.timeout,
            upload_timeout=self.config.upload_timeout,
        )
