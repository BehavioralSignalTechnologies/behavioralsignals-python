from typing import Iterator
from pathlib import Path

import grpc
import requests

from .types import APIError, ProcessItem, ProcessStatus, ResultResponse, StreamingOptions, ProcessListResponse
from .generated import api_pb2 as pb
from .generated import api_pb2_grpc as pb_grpc


API_URL = "https://api.behavioralsignals.com/v5"
STREAMING_API_URL = "https://streaming.behavioralsignals.com/v5"


class Client:
    def __init__(self, user_id: str, api_key: str):
        self.user_id = user_id
        self.api_key = api_key
        self._authenticate()

    def _headers(self, add_cid: bool = False):
        headers = {
            "accept": "application/json",
            "X-Auth-Token": self.api_key,
        }
        if add_cid:
            headers["X-Auth-Client"] = self.user_id
        return headers

    def _handle_response(self, response: requests.Response):
        if response.status_code != 200:
            try:
                error = APIError(**response.json())
                raise Exception(f"API Error {error.code}: {error.message}")
            except ValueError:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
        return response.json()

    def _authenticate(self):
        url = f"{API_URL}/auth"
        headers = self._headers(add_cid=True)
        response = requests.get(url, headers=headers)
        self._handle_response(response)

    def upload_audio(self, file_path: str) -> ProcessItem:
        """Uploads an audio file for processing and returns the process item.

        Args:
            file_path (str): Path to the audio file to upload.

        Returns:
            ProcessItem: The process item containing details about the submitted process.
        """

        UPLOAD_URL = f"{API_URL}/clients/{self.user_id}/processes/audio"
        headers = self._headers()

        file_name = Path(file_path).name
        with open(file_path, "rb") as audio_file:
            files = {"file": audio_file, "name": (None, file_name)}
            response = requests.post(UPLOAD_URL, headers=headers, files=files)
            data = self._handle_response(response)

        return ProcessItem(**data)

    def list_processes(self) -> ProcessListResponse:
        """Lists all processes for the authenticated user.

        Returns:
            ProcessListResponse: A list of processes associated with the user.
        """
        processes_url = f"{API_URL}/clients/{self.user_id}/processes"
        headers = self._headers()
        response = requests.get(processes_url, headers=headers)
        data = self._handle_response(response)

        return ProcessListResponse(processes=data)

    def get_process(self, pid: int) -> ProcessItem:
        """Retrieves details of a specific process by its ID.

        Args:
            pid (int): The process ID to retrieve.

        Returns:
            ProcessItem: The process item containing details about the specified process.
        """
        status_url = f"{API_URL}/clients/{self.user_id}/processes/{pid}"
        headers = self._headers()
        response = requests.get(status_url, headers=headers)
        data = self._handle_response(response)

        return ProcessItem(**data)

    def get_result(self, pid: int) -> ResultResponse:
        """Retrieves the result of a completed process by its ID.

        Args:
            pid (int): The process ID for which to retrieve the result
        Returns:
            ResultResponse: The result response containing the results of the specified process.
        """

        process = self.get_process(pid)
        if not process.is_completed:
            raise Exception(
                f"Process {pid} is not completed. Current status: {ProcessStatus(process.status).name}"
            )

        results_url = f"{API_URL}/clients/{self.user_id}/processes/{pid}/results"
        headers = self._headers()
        response = requests.get(results_url, headers=headers)
        data = self._handle_response(response)

        return ResultResponse(**data)

    def stream_audio(
        self, audio_stream: Iterator[bytes], options: StreamingOptions
    ) -> Iterator[pb.StreamResult]:

        with grpc.insecure_channel(STREAMING_API_URL) as channel:
            stub = pb_grpc.BehavioralStreamingApiStub(channel)

            def _request_generator() -> Iterator[pb.AudioStream]:
                # Streaming API always requires the first message to contain the audio configuration
                # and authentication details
                audio_config = options.to_pb_config()

                req = pb.AudioStream(
                    cid=int(self.user_id),
                    x_auth_token=self.api_key,
                    config=audio_config,
                )
                yield req

                for chunk in audio_stream:
                    yield pb.AudioStream(
                        cid=int(self.user_id),
                        x_auth_token=self.api_key,
                        audio_content=chunk,
                    )

            response_stream = stub.StreamAudio(_request_generator())
            for response in response_stream:
                yield response
