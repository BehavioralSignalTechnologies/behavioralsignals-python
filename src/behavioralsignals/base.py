from typing import Optional

import grpc
import requests

from .models import APIError
from .configuration import Configuration


class BaseClient:
    def __init__(self, cid: str, api_key: str):
        self.config = Configuration(cid=cid, api_key=api_key)
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
        headers: Optional[dict] = None,
        files: Optional[dict] = None,
    ):
        url = self.config.api_url + "/" + path
        if headers is None:
            headers = self._get_default_headers()

        if method == "GET":
            response = self.session.get(
                url, headers=headers, params=data, timeout=self.config.timeout
            )
        elif method == "POST":
            response = self.session.post(
                url, headers=headers, data=data, files=files, timeout=self.config.timeout
            )
        else:
            raise ValueError(f"Unsupported method: {method}")

        return self._handle_response(response)

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
