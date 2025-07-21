from typing import Literal, Iterator, Optional
from pathlib import Path

import grpc
import requests

from .types import (
    APIError,
    ProcessItem,
    ResultResponse,
    StreamingOptions,
    AudioUploadParams,
    ProcessListParams,
    ProcessListResponse,
)
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

    def upload_audio(
        self,
        file_path: str,
        name: Optional[str] = None,
        embeddings: bool = False,
        meta: Optional[str] = None,
    ) -> ProcessItem:
        """Uploads an audio file for processing and returns the process item.

        Args:
            file_path (str): Path to the audio file to upload.
            name (str, optional): Optional name for the job request. Defaults to filename.
            embeddings (bool): Whether to include speaker and behavioral embeddings. Defaults to False.
            meta (str, optional): Metadata json containing any extra user-defined metadata.
        Returns:
            ProcessItem: The process item containing details about the submitted process.
        """
        # Create and validate parameters
        params = AudioUploadParams(file_path=file_path, name=name, embeddings=embeddings, meta=meta)

        upload_url = f"{API_URL}/clients/{self.user_id}/processes/audio"
        headers = self._headers()

        # Use provided name or default to filename
        job_name = params.name or Path(params.file_path).name
        with open(params.file_path, "rb") as audio_file:
            files = {"file": audio_file}
            data = {"name": job_name, "embeddings": params.embeddings}
            # Only include meta if provided
            if params.meta:
                data["meta"] = params.meta

            response = requests.post(upload_url, headers=headers, files=files, data=data)
            data = self._handle_response(response)

        return ProcessItem(**data)

    def list_processes(
        self,
        page: int = 0,
        page_size: int = 1000,
        sort: Literal["asc", "desc"] = "asc",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> ProcessListResponse:
        """Lists all processes for the authenticated user.

        Args:
            page (int): Page number for pagination (default is 0).
            page_size (int): Number of processes per page (default is 1000).
            sort (str): Sort order for the processes, should be "asc" or "desc". Defaults to "asc".
            start_date (str, optional: Filter processes created on or after this date (YYYY-MM-DD).
            end_date (str, optional): Filter processes created on or before this date (YYYY-MM-DD).
        Returns:
            ProcessListResponse: A list of processes associated with the user.
        """
        processes_url = f"{API_URL}/clients/{self.user_id}/processes"
        headers = self._headers()

        query_params = ProcessListParams(
            page=page, page_size=page_size, sort=sort, start_date=start_date, end_date=end_date
        )
        query_params = query_params.model_dump(by_alias=True, exclude_none=True)
        response = requests.get(processes_url, headers=headers, params=query_params)
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
                # Streaming API always requires the first message to contain
                # the audio configurationand authentication details
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
