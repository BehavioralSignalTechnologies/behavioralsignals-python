from typing import Literal, Iterator, Optional
from pathlib import Path

from google.protobuf.json_format import MessageToDict

from .base import BaseClient
from .models import (
    ProcessItem,
    ResultResponse,
    StreamingOptions,
    AudioUploadParams,
    ProcessListParams,
    ProcessListResponse,
    StreamingResultResponse,
)
from .generated import api_pb2 as pb
from .generated import api_pb2_grpc as pb_grpc


class Behavioral(BaseClient):
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

        # Use provided name or default to filename
        job_name = params.name or Path(params.file_path).name

        with open(params.file_path, "rb") as audio_file:
            files = {"file": audio_file}
            data = {"name": job_name, "embeddings": params.embeddings}

            if params.meta:
                data["meta"] = params.meta

            data = self._send_request(
                path=f"clients/{self.config.cid}/processes/audio",
                method="POST",
                files=files,
                data=data,
            )

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

        query_params = ProcessListParams(
            page=page, page_size=page_size, sort=sort, start_date=start_date, end_date=end_date
        )
        query_params = query_params.model_dump(by_alias=True, exclude_none=True)

        data = self._send_request(
            path=f"clients/{self.config.cid}/processes",
            method="GET",
            data=query_params,
        )

        return ProcessListResponse(processes=data)

    def get_process(self, pid: int) -> ProcessItem:
        """Retrieves details of a specific process by its ID.

        Args:
            pid (int): The process ID to retrieve.
        Returns:
            ProcessItem: The process item containing details about the specified process.
        """

        data = self._send_request(
            path=f"clients/{self.config.cid}/processes/{pid}",
            method="GET",
        )

        return ProcessItem(**data)

    def get_result(self, pid: int) -> ResultResponse:
        """Retrieves the result of a completed process by its ID.

        Args:
            pid (int): The process ID for which to retrieve the result
        Returns:
            ResultResponse: The result response containing the results of the specified process.
        """
        data = self._send_request(
            path=f"clients/{self.config.cid}/processes/{pid}/results",
            method="GET",
        )
        return ResultResponse(**data)

    def stream_audio(
        self, audio_stream: Iterator[bytes], options: StreamingOptions
    ) -> Iterator[ResultResponse]:
        with self._get_channel_context() as channel:
            stub = pb_grpc.BehavioralStreamingApiStub(channel)

            def _request_generator() -> Iterator[pb.AudioStream]:
                # Streaming API always requires the first message to contain
                # the audio configurationand authentication details
                audio_config = options.to_pb_config()
                req = pb.AudioStream(
                    cid=int(self.config.cid),
                    x_auth_token=self.config.api_key,
                    config=audio_config,
                )
                yield req

                for chunk in audio_stream:
                    yield pb.AudioStream(
                        cid=int(self.config.cid),
                        x_auth_token=self.config.api_key,
                        audio_content=chunk,
                    )

            response_stream = stub.StreamAudio(_request_generator())
            for response in response_stream:
                resp_dict = MessageToDict(response, always_print_fields_with_no_presence=True)
                response_data = StreamingResultResponse(**resp_dict)
                yield response_data
