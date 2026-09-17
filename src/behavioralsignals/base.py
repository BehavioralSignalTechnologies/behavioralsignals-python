import time
from typing import Callable, Optional

import grpc
import requests

from .models import APIError, ProcessItem, ProcessStatus
from .configuration import DEFAULT_TIMEOUT, DEFAULT_UPLOAD_TIMEOUT, TimeoutType, Configuration


POLL_INTERVAL_SECONDS = 1.0


class BaseClient:
    def __init__(
        self,
        cid: str,
        api_key: str,
        timeout: Optional[TimeoutType] = DEFAULT_TIMEOUT,
        upload_timeout: Optional[TimeoutType] = DEFAULT_UPLOAD_TIMEOUT,
    ):
        """Creates a client and checks your credentials with the API.

        Args:
            cid (str): Your client ID.
            api_key (str): Your API key.
            timeout (float or tuple, optional): Seconds to wait on each HTTP request, as one number
                or a (connect, read) pair. Defaults to (10, 60). None means no limit.
                This is not the total wait of `wait_for_result`, which has its own `timeout`.
            upload_timeout (float or tuple, optional): Same as `timeout`, for upload requests.
                Defaults to (10, 300).
        """
        self.config = Configuration(
            cid=cid, api_key=api_key, timeout=timeout, upload_timeout=upload_timeout
        )
        self.session = requests.Session()
        self._authenticate()

    def _get_default_headers(self):
        headers = {
            "accept": "application/json",
            "X-Auth-Token": self.config.api_key,
        }
        return headers

    def _handle_response(self, response: requests.Response) -> dict:
        if response.status_code != 200:
            try:
                error = APIError(**response.json())
                raise Exception(f"API Error {error.code}: {error.message}")
            except ValueError:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
        return response.json()

    def _authenticate(self):
        headers = self._get_default_headers()
        headers["X-Auth-Client"] = self.config.cid
        response = self._send_request(path="auth", method="GET", headers=headers)
        return response

    def _send_request(
        self,
        path: str,
        method: str = "GET",
        data: Optional[dict] = None,
        json: Optional[dict] = None,
        headers: Optional[dict] = None,
        files: Optional[dict] = None,
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
        self, get_process: Callable[[int], ProcessItem], pid: int, timeout: Optional[float]
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
        self, get_process: Callable[[int], ProcessItem], pid: int, deadline: Optional[float]
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
