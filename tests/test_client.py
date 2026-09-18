from datetime import date
from collections import namedtuple

import pytest
import requests

from behavioralsignals import Client, Deepfakes, Behavioral, BehavioralSignalsError


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self.body = body
        self.text = text

    def json(self):
        if self.body is None:
            raise requests.JSONDecodeError("Expecting value", self.text, 0)
        return self.body


API_URL = "https://api.behavioralsignals.com/v5"
S3_URL = "https://example.com/a.wav"

Request = namedtuple("Request", "method url headers timeout params data files json")


def fake_requests(monkeypatch, response=None):
    """Replaces HTTP calls with fakes. Returns the requests that were sent."""
    calls = []
    response = response or FakeResponse(body={"pid": 1})

    def record(method, url, kwargs):
        calls.append(
            Request(
                method,
                url,
                kwargs["headers"],
                kwargs["timeout"],
                kwargs.get("params"),
                kwargs.get("data"),
                kwargs.get("files"),
                kwargs.get("json"),
            )
        )
        return response

    def fake_get(self, url, **kwargs):
        return record("GET", url, kwargs)

    def fake_post(self, url, **kwargs):
        return record("POST", url, kwargs)

    monkeypatch.setattr(requests.Session, "get", fake_get)
    monkeypatch.setattr(requests.Session, "post", fake_post)
    return calls


def timeouts(calls):
    return [(call.method, call.timeout) for call in calls]


@pytest.fixture
def audio_file(tmp_path):
    path = tmp_path / "audio.wav"
    path.write_bytes(b"fake audio")
    return str(path)


@pytest.fixture
def no_env_credentials(monkeypatch):
    monkeypatch.delenv("BEHAVIORALSIGNALS_CID", raising=False)
    monkeypatch.delenv("BEHAVIORALSIGNALS_API_KEY", raising=False)


def test_client_has_default_request_timeout(monkeypatch):
    calls = fake_requests(monkeypatch)
    Client(cid="1", api_key="k")
    assert timeouts(calls) == [("GET", (10.0, 60.0))]


def test_client_timeout_reaches_sub_clients(monkeypatch):
    calls = fake_requests(monkeypatch)
    client = Client(cid="1", api_key="k", timeout=5)
    assert client.behavioral.config.timeout == 5
    assert timeouts(calls) == [("GET", 5), ("GET", 5)]


def test_client_timeout_none_disables_it(monkeypatch):
    calls = fake_requests(monkeypatch)
    client = Client(cid="1", api_key="k", timeout=None, upload_timeout=None)
    client.deepfakes.upload_s3_presigned_url(url="https://example.com/a.wav")
    assert timeouts(calls) == [("GET", None), ("GET", None), ("POST", None)]


def test_uploads_use_upload_timeout(monkeypatch, audio_file):
    calls = fake_requests(monkeypatch)
    client = Client(cid="1", api_key="k")
    client.behavioral.upload_audio(file_path=audio_file)
    client.behavioral.upload_s3_presigned_url(url="https://example.com/a.wav")
    client.deepfakes.upload_audio(file_path=audio_file)
    client.deepfakes.upload_s3_presigned_url(url="https://example.com/a.wav")
    client.deepfakes.upload_video(file_path=audio_file)
    client.deepfakes.upload_s3_presigned_video_url(url="https://example.com/a.mp4")
    posts = [call.timeout for call in calls if call.method == "POST"]
    assert posts == [(10.0, 300.0)] * 6


def test_upload_timeout_reaches_sub_clients(monkeypatch):
    calls = fake_requests(monkeypatch)
    client = Client(cid="1", api_key="k", upload_timeout=(10, 900))
    client.deepfakes.upload_s3_presigned_video_url(url="https://example.com/a.mp4")
    assert timeouts(calls)[-1] == ("POST", (10.0, 900.0))


def test_sub_clients_are_created_once(monkeypatch):
    fake_requests(monkeypatch)
    client = Client(cid="1", api_key="k")
    assert isinstance(client.behavioral, Behavioral)
    assert isinstance(client.deepfakes, Deepfakes)
    assert client.behavioral is client.behavioral


def test_client_reads_credentials_from_env(monkeypatch):
    fake_requests(monkeypatch)
    monkeypatch.setenv("BEHAVIORALSIGNALS_CID", "123")
    monkeypatch.setenv("BEHAVIORALSIGNALS_API_KEY", "env-key")
    client = Client()
    assert (client.config.cid, client.config.api_key) == ("123", "env-key")
    assert (client.behavioral.config.cid, client.behavioral.config.api_key) == ("123", "env-key")


def test_passed_credentials_win_over_env(monkeypatch):
    fake_requests(monkeypatch)
    monkeypatch.setenv("BEHAVIORALSIGNALS_CID", "123")
    monkeypatch.setenv("BEHAVIORALSIGNALS_API_KEY", "env-key")
    client = Client(cid="456", api_key="passed-key")
    assert (client.config.cid, client.config.api_key) == ("456", "passed-key")


def test_missing_cid_raises_clear_error(monkeypatch, no_env_credentials):
    fake_requests(monkeypatch)
    with pytest.raises(ValueError, match="BEHAVIORALSIGNALS_CID"):
        Client(api_key="k")


def test_missing_api_key_raises_clear_error(monkeypatch, no_env_credentials):
    fake_requests(monkeypatch)
    with pytest.raises(ValueError, match="BEHAVIORALSIGNALS_API_KEY"):
        Client(cid="1")


def test_api_error_raises_sdk_error(monkeypatch):
    fake_requests(monkeypatch, FakeResponse(401, body={"code": 401, "message": "bad key"}))
    with pytest.raises(BehavioralSignalsError, match="API Error 401: bad key") as error:
        Client(cid="1", api_key="k")
    assert error.value.status_code == 401


def test_http_error_without_json_raises_sdk_error(monkeypatch):
    fake_requests(monkeypatch, FakeResponse(500, text="Internal error"))
    with pytest.raises(BehavioralSignalsError, match="HTTP 500: Internal error") as error:
        Client(cid="1", api_key="k")
    assert error.value.status_code == 500


@pytest.mark.parametrize("body", [["gateway down"], "gateway down"])
def test_http_error_with_unexpected_json_raises_sdk_error(monkeypatch, body):
    fake_requests(monkeypatch, FakeResponse(502, body=body, text="gateway down"))
    with pytest.raises(BehavioralSignalsError, match="HTTP 502: gateway down"):
        Client(cid="1", api_key="k")


def test_empty_env_credential_raises_clear_error(monkeypatch):
    fake_requests(monkeypatch)
    monkeypatch.setenv("BEHAVIORALSIGNALS_CID", "1")
    monkeypatch.setenv("BEHAVIORALSIGNALS_API_KEY", "")
    with pytest.raises(ValueError, match="BEHAVIORALSIGNALS_API_KEY"):
        Client()


def test_cid_can_be_an_int(monkeypatch):
    fake_requests(monkeypatch)
    client = Client(cid=12345, api_key="k")
    assert client.config.cid == "12345"


def test_close_closes_sub_client_sessions(monkeypatch):
    fake_requests(monkeypatch)
    closed = []

    def record_close(session):
        closed.append(session)

    monkeypatch.setattr(requests.Session, "close", record_close)
    with Client(cid="1", api_key="k") as client:
        sessions = [client.session, client.behavioral.session, client.deepfakes.session]
    assert {id(session) for session in closed} == {id(session) for session in sessions}


def test_close_does_not_create_unused_sub_clients(monkeypatch):
    calls = fake_requests(monkeypatch)
    Client(cid="1", api_key="k").close()
    assert timeouts(calls) == [("GET", (10.0, 60.0))]


@pytest.mark.parametrize(
    ("failing", "working"), [("behavioral", "deepfakes"), ("deepfakes", "behavioral")]
)
def test_close_closes_the_other_sessions_when_one_fails(monkeypatch, failing, working):
    fake_requests(monkeypatch)
    closed = []

    def record_close(session):
        closed.append(session)

    def fail():
        raise RuntimeError("boom")

    monkeypatch.setattr(requests.Session, "close", record_close)
    client = Client(cid="1", api_key="k")
    sessions = [client.session, getattr(client, working).session]
    getattr(client, failing).close = fail
    with pytest.raises(RuntimeError, match="boom"):
        client.close()
    assert {id(session) for session in closed} == {id(session) for session in sessions}


def test_requests_carry_the_credentials(monkeypatch):
    calls = fake_requests(monkeypatch)
    client = Client(cid="123", api_key="secret")
    client.behavioral.get_process(pid=7)
    assert calls[0].headers["X-Auth-Client"] == "123"
    assert {call.headers["X-Auth-Token"] for call in calls} == {"secret"}


@pytest.mark.parametrize(
    ("upload", "path"),
    [
        (
            lambda client, file: client.behavioral.upload_audio(file_path=file),
            "clients/1/processes/audio",
        ),
        (
            lambda client, _: client.behavioral.upload_s3_presigned_url(url=S3_URL),
            "clients/1/processes/s3-presigned-url",
        ),
        (
            lambda client, file: client.deepfakes.upload_audio(file_path=file),
            "detection/clients/1/processes/audio",
        ),
        (
            lambda client, _: client.deepfakes.upload_s3_presigned_url(url=S3_URL),
            "detection/clients/1/processes/s3-presigned-url",
        ),
        (
            lambda client, file: client.deepfakes.upload_video(file_path=file),
            "detection/clients/1/processes/video",
        ),
        (
            lambda client, _: client.deepfakes.upload_s3_presigned_video_url(url=S3_URL),
            "detection/clients/1/processes/s3-presigned-video-url",
        ),
    ],
)
def test_uploads_post_to_their_endpoint(monkeypatch, audio_file, upload, path):
    calls = fake_requests(monkeypatch)
    upload(Client(cid="1", api_key="k"), audio_file)
    assert (calls[-1].method, calls[-1].url) == ("POST", f"{API_URL}/{path}")


@pytest.mark.parametrize(
    ("api", "path"),
    [
        ("behavioral", "clients/1/processes/7/results"),
        ("deepfakes", "detection/clients/1/processes/7/results"),
    ],
)
def test_get_result_parses_the_response(monkeypatch, api, path):
    body = {
        "pid": 7,
        "cid": 1,
        "results": [
            {"startTime": "0.487", "endTime": "3.001", "task": "emotion", "finalLabel": "sad"}
        ],
    }
    calls = fake_requests(monkeypatch, FakeResponse(body=body))
    output = getattr(Client(cid="1", api_key="k"), api).get_result(pid=7)
    assert calls[-1].url == f"{API_URL}/{path}"
    assert output.pid == 7
    assert [(item.st, item.et, item.task, item.finalLabel) for item in output.results] == [
        (0.487, 3.001, "emotion", "sad")
    ]


def test_get_video_result_parses_both_result_lists(monkeypatch):
    body = {
        "pid": 7,
        "audio_results": [{"task": "deepfake", "finalLabel": "fake"}],
        "video_results": [{"task": "deepfake", "finalLabel": "real"}],
    }
    calls = fake_requests(monkeypatch, FakeResponse(body=body))
    output = Client(cid="1", api_key="k").deepfakes.get_video_result(pid=7)
    assert calls[-1].url == f"{API_URL}/detection/clients/1/processes/video/7/results"
    assert [item.finalLabel for item in output.audio_results] == ["fake"]
    assert [item.finalLabel for item in output.video_results] == ["real"]


def test_list_processes_parses_the_response(monkeypatch):
    body = [
        {"pid": 7, "status": 2, "name": "done.wav"},
        {"pid": 8, "status": 1, "name": "running.wav"},
    ]
    calls = fake_requests(monkeypatch, FakeResponse(body=body))
    output = Client(cid="1", api_key="k").behavioral.list_processes()
    assert calls[-1].url == f"{API_URL}/clients/1/processes"
    assert output.total_count == 2
    assert [process.pid for process in output.completed_processes()] == [7]
    assert [process.pid for process in output.processing_processes()] == [8]


@pytest.mark.parametrize(
    ("list_processes", "path"),
    [
        (lambda client: client.behavioral.list_processes, "clients/1/processes"),
        (lambda client: client.deepfakes.list_processes, "detection/clients/1/processes"),
        (
            lambda client: client.deepfakes.list_video_processes,
            "detection/clients/1/processes/video",
        ),
    ],
)
def test_list_processes_sends_the_query_parameters(monkeypatch, list_processes, path):
    calls = fake_requests(monkeypatch, FakeResponse(body=[]))
    client = Client(cid="1", api_key="k")
    list_processes(client)(page=2, page_size=50, sort="desc", start_date="2026-01-01")
    assert (calls[-1].method, calls[-1].url) == ("GET", f"{API_URL}/{path}")
    assert calls[-1].params == {
        "page": 2,
        "pageSize": 50,
        "sort": "desc",
        "startDate": date(2026, 1, 1),
    }


@pytest.mark.parametrize(
    ("upload", "extra_fields"),
    [
        (lambda client, file: client.behavioral.upload_audio(file_path=file), {}),
        (
            lambda client, file: client.deepfakes.upload_audio(file_path=file),
            {"enable_generator_detection": False},
        ),
        (
            lambda client, file: client.deepfakes.upload_video(file_path=file),
            {"enable_generator_detection": False},
        ),
    ],
    ids=["behavioral-audio", "deepfakes-audio", "deepfakes-video"],
)
def test_file_uploads_send_the_file_and_the_form_fields(
    monkeypatch, audio_file, upload, extra_fields
):
    calls = fake_requests(monkeypatch)
    upload(Client(cid="1", api_key="k"), audio_file)
    assert calls[-1].files["file"].name == audio_file
    assert calls[-1].data == {"name": "audio.wav", "embeddings": False, **extra_fields}


@pytest.mark.parametrize(
    ("upload", "extra_fields"),
    [
        (lambda client: client.behavioral.upload_s3_presigned_url(url=S3_URL, name="job"), {}),
        (
            lambda client: client.deepfakes.upload_s3_presigned_url(url=S3_URL, name="job"),
            {"enable_generator_detection": False},
        ),
        (
            lambda client: client.deepfakes.upload_s3_presigned_video_url(url=S3_URL, name="job"),
            {"enable_generator_detection": False},
        ),
    ],
    ids=["behavioral-url", "deepfakes-url", "deepfakes-video-url"],
)
def test_url_uploads_send_the_payload_as_json(monkeypatch, upload, extra_fields):
    calls = fake_requests(monkeypatch)
    upload(Client(cid="1", api_key="k"))
    assert calls[-1].json == {
        "url": S3_URL,
        "name": "job",
        "embeddings": False,
        **extra_fields,
    }
    assert calls[-1].headers["content-type"] == "application/json"


@pytest.mark.parametrize(
    ("get_process", "path"),
    [
        (lambda client: client.behavioral.get_process(pid=7), "clients/1/processes/7"),
        (lambda client: client.deepfakes.get_process(pid=7), "detection/clients/1/processes/7"),
        (
            lambda client: client.deepfakes.get_video_process(pid=7),
            "detection/clients/1/processes/video/7",
        ),
    ],
)
def test_get_process_parses_the_response(monkeypatch, get_process, path):
    body = {"pid": 7, "cid": 1, "name": "a.wav", "status": 2, "duration": 3.5}
    calls = fake_requests(monkeypatch, FakeResponse(body=body))
    process = get_process(Client(cid="1", api_key="k"))
    assert calls[-1].url == f"{API_URL}/{path}"
    assert (process.pid, process.name, process.duration) == (7, "a.wav", 3.5)
    assert process.is_completed
