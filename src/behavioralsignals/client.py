from typing import Iterator
from pathlib import Path

import grpc
import requests

from .generated import api_pb2 as pb
from .generated import api_pb2_grpc as pb_grpc


API_URL = "https://api.behavioralsignals.com/v5"
STREAMING_API_URL = "https://streaming.behavioralsignals.com/v5"


class Client:
    def __init__(self, user_id: str, api_key: str):
        self.user_id = user_id
        self.api_key = api_key
        self._auth()

    def _auth(self):
        url = f"{API_URL}/auth"
        headers = {
            "accept": "application/json",
            "X-Auth-Client": self.user_id,
            "X-Auth-Token": self.api_key,
        }
        response = requests.get(url, headers=headers)
        code = response.status_code
        if code == 200:
            print("Authentication successful")
        elif code == 401:
            raise Exception("Authentication failed: Invalid credentials")

    def send_audio(self, file_path: str) -> str:
        UPLOAD_URL = f"{API_URL}/clients/{self.user_id}/processes/audio"
        headers = {"accept": "application/json", "X-Auth-Token": self.api_key}

        file_name = Path(file_path).name
        with open(file_path, "rb") as audio_file:
            files = {"file": audio_file, "name": (None, file_name)}
            response = requests.post(UPLOAD_URL, headers=headers, files=files)
        if response.status_code != 200:
            raise Exception(f"Failed to upload audio file: {response.status_code} - {response.text}")

        return response.json()

    def check_process_status(self, pid: int) -> str:
        status_url = f"{API_URL}/clients/{self.user_id}/processes/{pid}"
        headers = {"accept": "application/json", "X-Auth-Token": self.api_key}
        response = requests.get(status_url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Failed to check process status: {response.status_code} - {response.text}")
        return response.json()

    def get_result(self, pid: int) -> str:
        results_url = f"{API_URL}/clients/{self.user_id}/processes/{pid}/results"
        headers = {"accept": "application/json", "X-Auth-Token": self.api_key}
        results_response = requests.get(results_url, headers=headers)
        if results_response.status_code != 200:
            raise Exception(f"Failed to get results: {results_response.status_code} - {results_response.text}")
        return results_response.json()

    def stream_audio(self, audio_stream: Iterator[bytes], streaming_options: dict) -> Iterator[pb.StreamResult]:
        with grpc.insecure_channel(STREAMING_API_URL) as channel:
            stub = pb_grpc.BehavioralStreamingApiStub(channel)
            sample_rate = streaming_options.get("sample_rate", 16000)
            levels_dict = {
                "segment": pb.Level.segment,
                "utterance": pb.Level.utterance,
            }
            level = streaming_options.get("level")
            if level not in levels_dict:
                level = None
            else:
                level = levels_dict[level]

            def _request_generator() -> Iterator[pb.AudioStream]:
                # Streaming API always requires the first message to contain the audio configuration
                # and authentication details
                audio_config = pb.AudioConfig(sample_rate_hertz=sample_rate)
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
