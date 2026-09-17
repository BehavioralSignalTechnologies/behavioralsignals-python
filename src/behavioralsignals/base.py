import os
import time
from collections.abc import Callable

import grpc
import requests

from .models import APIError, ProcessItem, ProcessStatus
from .configuration import DEFAULT_TIMEOUT, DEFAULT_UPLOAD_TIMEOUT, TimeoutType, Configuration


POLL_INTERVAL_SECONDS = 1.0


class BehavioralSignalsError(Exception):
    """Raised when the API returns an error response."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def _value_or_env(value: str | int | None, arg_name: str, env_var: str) -> str:
    """Returns the value, or the environment variable if the value is not given."""
    if value is None:
        value = os.environ.get(env_var)
    if not value:
        raise ValueError(f"Missing {arg_name}: pass it or set the {env_var} environment variable")
    return str(value)


class BaseClient:
    def __init__(
        self,
        cid: str | int | None = None,
        api_key: str | None = None,
        timeout: TimeoutType | None = DEFAULT_TIMEOUT,
        upload_timeout: TimeoutType | None = DEFAULT_UPLOAD_TIMEOUT,
    ):
        """Creates a client and checks your credentials with the API.

        Args:
            cid (str or int, optional): Your client ID. Defaults to the BEHAVIORALSIGNALS_CID
                environment variable.
            api_key (str, optional): Your API key. Defaults to the BEHAVIORALSIGNALS_API_KEY
                environment variable.
            timeout (float or tuple, optional): Seconds to wait on each HTTP request, as one number
                or a (connect, read) pair. Defaults to (10, 60). None means no limit.
                This is not the total wait of `wait_for_result`, which has its own `timeout`.
            upload_timeout (float or tuple, optional): Same as `timeout`, for upload requests.
                Defaults to (10, 300).

        Raises:
            ValueError: If cid or api_key is not passed and its environment variable is not set.
            BehavioralSignalsError: If the API rejects the credentials.
        """
        self.config = Configuration(
            cid=_value_or_env(cid, "cid", "BEHAVIORALSIGNALS_CID"),
            api_key=_value_or_env(api_key, "api_key", "BEHAVIORALSIGNALS_API_KEY"),
            timeout=timeout,
            upload_timeout=upload_timeout,
        )
        self.session = requests.Session()
        self._authenticate()

    def _get_default_headers(self):
        return {
            "accept": "application/json",
            "X-Auth-Token": self.config.api_key,
        }

    def _handle_response(self, response: requests.Response) -> dict:
        if response.status_code != 200:
            try:
                error = APIError(**response.json())
                raise BehavioralSignalsError(
                    f"API Error {error.code}: {error.message}", response.status_code
                )
            except (ValueError, TypeError):
                raise BehavioralSignalsError(
                    f"HTTP {response.status_code}: {response.text}", response.status_code
                ) from None
        return response.json()

    def _authenticate(self):
        headers = self._get_default_headers()
        headers["X-Auth-Client"] = self.config.cid
        return self._send_request(path="auth", method="GET", headers=headers)

    def _send_request(
        self,
        path: str,
        method: str = "GET",
        data: dict | None = None,
        json: dict | None = None,
        headers: dict | None = None,
        files: dict | None = None,
    ):
        url = self.config.api_url + "/" + path
        if headers is None:
            headers = self._get_default_headers()
        else:
            headers = {**self._get_default_headers(), **headers}

        if method == "GET":
            response = self.session.get(
                url, headers=headers, params=data, timeout=self.config.timeout
            )
        elif method == "POST":
            # Every POST request is an upload
            response = self.session.post(
                url,
                headers=headers,
                data=data,
                files=files,
                json=json,
                timeout=self.config.upload_timeout,
            )
        else:
            raise ValueError(f"Unsupported method: {method}")

        return self._handle_response(response)

    def _wait_for_process(
        self, get_process: Callable[[int], ProcessItem], pid: int, timeout: float | None
    ) -> None:
        """Polls a process until it is no longer pending or processing.

        Raises:
            TimeoutError: If the process is still running after `timeout` seconds.
            RuntimeError: If the process ends without completing (e.g. failed).
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        process = self._get_process_with_retry(get_process, pid, deadline)
        while process.status in (ProcessStatus.PENDING, ProcessStatus.PROCESSING):
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Process {pid} is still running after {timeout} seconds; "
                    "you can wait for it again"
                )
            time.sleep(POLL_INTERVAL_SECONDS)
            process = self._get_process_with_retry(get_process, pid, deadline)
        if not process.is_completed:
            raise RuntimeError(f"Process {pid} did not complete: {process.statusmsg}")

    def _get_process_with_retry(
        self, get_process: Callable[[int], ProcessItem], pid: int, deadline: float | None
    ) -> ProcessItem:
        """Gets a process, retrying connection errors and timeouts until the deadline passes."""
        while True:
            try:
                return get_process(pid)
            except (requests.ConnectionError, requests.Timeout):
                if deadline is not None and time.monotonic() >= deadline:
                    raise
                time.sleep(POLL_INTERVAL_SECONDS)

    def close(self):
        """Close the session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _get_channel_context(self):
        """Returns the channel context for gRPC connections."""
        if self.config.use_ssl:
            credentials = grpc.ssl_channel_credentials()
            return grpc.secure_channel(self.config.streaming_api_url, credentials=credentials)
        else:
            return grpc.insecure_channel(self.config.streaming_api_url)
