import os
import sys
import subprocess
from types import SimpleNamespace
from datetime import datetime

import pytest
import requests
from mcp import Client

from behavioralsignals import BehavioralSignalsError, mcp_server
from behavioralsignals.models import (
    ResultItem,
    ProcessItem,
    ResultResponse,
    ModelPredictions,
    ProcessListResponse,
    VideoResultResponse,
)


pytestmark = pytest.mark.anyio
HOME_FILE = os.path.expanduser("~/call.wav")


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeApi:
    """Stands in for Behavioral and Deepfakes: records calls and returns canned responses."""

    def __init__(self):
        self.built = []  # names of the classes the server created
        self.calls = []  # (method name, kwargs)
        self.responses = {}  # method name -> return value, or an exception to raise

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def method(*args, **kwargs):
            self.calls.append((name, kwargs))
            response = self.responses.get(name, ProcessItem(pid=7))
            if isinstance(response, Exception):
                raise response
            return response

        return method


@pytest.fixture
def api(monkeypatch):
    fake = FakeApi()
    monkeypatch.setattr(mcp_server, "Behavioral", lambda: fake.built.append("Behavioral") or fake)
    monkeypatch.setattr(mcp_server, "Deepfakes", lambda: fake.built.append("Deepfakes") or fake)
    return fake


def item(task, label=None, posterior=None, score=None, start="0.5", end="1.5"):
    prediction = [ModelPredictions(label=label, posterior=posterior, score=score)]
    return ResultItem(
        startTime=start, endTime=end, task=task, finalLabel=label, prediction=prediction
    )


def emotions(count):
    return ResultResponse(pid=7, results=[item("emotion", "sad", "0.7") for _ in range(count)])


async def call(tool, **args):
    async with Client(mcp_server.server) as client:
        result = await client.call_tool(tool, args)
    return result.is_error, result.content[0].text


@pytest.mark.parametrize(
    ("analysis", "built", "method"),
    [
        ("behavioral", "Behavioral", "wait_for_result"),
        ("deepfake_audio", "Deepfakes", "wait_for_result"),
        ("deepfake_video", "Deepfakes", "wait_for_video_result"),
    ],
)
async def test_get_result_uses_the_api_of_the_analysis(api, analysis, built, method):
    api.responses[method] = TimeoutError("still running")
    await call("get_result", pid=7, analysis=analysis, wait_seconds=0)
    assert api.built == [built]
    assert api.calls == [(method, {"pid": 7, "timeout": 0.0})]


async def test_formats_labelled_rows_and_drops_the_rest(api):
    api.responses["wait_for_result"] = ResultResponse(
        pid=7,
        results=[
            item("asr", "Hello there."),
            item("emotion", "sad", "0.706"),
            item("intensity", score="0.62"),
            item("features"),
            ResultItem(task="language", prediction=[]),
        ],
    )
    is_error, text = await call("get_result", pid=7, analysis="behavioral")
    assert not is_error
    assert text == (
        "pid 7 completed. Rows 1-3 of 3. Tasks: asr, emotion, intensity\n"
        "start\tend\ttask\tlabel\tconfidence\n"
        "0.5\t1.5\tasr\tHello there.\t\n"
        "0.5\t1.5\temotion\tsad\t0.706\n"
        "0.5\t1.5\tintensity\t0.62\t"
    )


async def test_tabs_and_newlines_in_a_cell_become_spaces(api):
    api.responses["wait_for_result"] = ResultResponse(
        pid=7, results=[item("asr", "Hi\tthere.\nBye.")]
    )
    _, text = await call("get_result", pid=7, analysis="behavioral")
    assert text.splitlines()[2] == "0.5\t1.5\tasr\tHi there. Bye.\t"


async def test_video_rows_have_a_track_column(api):
    api.responses["wait_for_video_result"] = VideoResultResponse(
        pid=7,
        audio_results=[item("deepfake", "bonafide", "0.9")],
        video_results=[item("visual_deepfake", "spoofed", "0.8")],
    )
    _, text = await call("get_result", pid=7, analysis="deepfake_video")
    assert text.splitlines()[1:] == [
        "track\tstart\tend\ttask\tlabel\tconfidence",
        "audio\t0.5\t1.5\tdeepfake\tbonafide\t0.9",
        "video\t0.5\t1.5\tvisual_deepfake\tspoofed\t0.8",
    ]


async def test_pages_rows_with_offset_and_limit(api):
    api.responses["wait_for_result"] = emotions(5)
    _, first = await call("get_result", pid=7, analysis="behavioral", limit=2)
    _, last = await call("get_result", pid=7, analysis="behavioral", offset=4)
    _, past = await call("get_result", pid=7, analysis="behavioral", offset=5)
    assert first.startswith("pid 7 completed. Rows 1-2 of 5.")
    assert first.endswith('More rows: get_result(pid=7, analysis="behavioral", offset=2)')
    assert last.startswith("pid 7 completed. Rows 5-5 of 5.") and "More rows" not in last
    assert past == "pid 7 completed. No rows at offset 5; there are 5 rows."


async def test_tasks_filter_keeps_those_tasks_and_the_more_hint_repeats_it(api):
    api.responses["wait_for_result"] = ResultResponse(
        pid=7, results=[item("asr", "Hi."), item("emotion", "sad"), item("emotion", "happy")]
    )
    _, text = await call("get_result", pid=7, analysis="behavioral", tasks=["emotion"], limit=1)
    _, none = await call("get_result", pid=7, analysis="behavioral", tasks=["gender"])
    assert text.splitlines()[0] == "pid 7 completed. Rows 1-1 of 2. Tasks: asr, emotion"
    assert text.splitlines()[2] == "0.5\t1.5\temotion\tsad\t"
    assert text.endswith(
        'More rows: get_result(pid=7, analysis="behavioral", tasks=["emotion"], offset=1)'
    )
    assert none == "pid 7 completed. No result rows. Tasks: asr, emotion"


async def test_still_processing_returns_the_pid_to_check_later(api):
    api.responses["wait_for_video_result"] = TimeoutError("still running")
    is_error, text = await call("get_result", pid=9, analysis="deepfake_video", wait_seconds=0)
    assert not is_error
    assert text == (
        'pid 9 is still processing. Call get_result(pid=9, analysis="deepfake_video") to wait again.'
    )


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("Process 7 did not complete: not enough credits"),
        BehavioralSignalsError("API Error 404: process not found", status_code=404),
        requests.ConnectionError("connection refused"),
    ],
)
async def test_errors_reach_the_model(api, error):
    api.responses["wait_for_result"] = error
    is_error, text = await call("get_result", pid=7, analysis="behavioral")
    assert is_error and str(error) in text


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("get_result", {"pid": 7, "analysis": "behavioral"}),
        ("analyze_behavior", {"source": "/data/call.wav"}),
    ],
)
async def test_failed_job_shows_only_the_first_line_of_its_reason(api, tool, args):
    reason = "Process 7 did not complete: bad audio\n\nffmpeg log"
    api.responses["wait_for_result"] = RuntimeError(reason)
    is_error, text = await call(tool, **args)
    assert is_error and text.endswith("Process 7 did not complete: bad audio")


async def test_wait_seconds_stays_below_client_timeouts(api):
    is_error, text = await call("get_result", pid=7, analysis="behavioral", wait_seconds=51)
    assert is_error and "less than or equal to 50" in text
    assert api.calls == []


async def test_missing_credentials_reach_the_model(monkeypatch):
    monkeypatch.delenv("BEHAVIORALSIGNALS_CID", raising=False)
    monkeypatch.delenv("BEHAVIORALSIGNALS_API_KEY", raising=False)
    is_error, text = await call("get_result", pid=7, analysis="behavioral")
    assert is_error and "BEHAVIORALSIGNALS_CID" in text


def test_sdk_import_does_not_load_mcp():
    code = "import sys, behavioralsignals; assert 'mcp' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_missing_mcp_package_gives_an_install_hint():
    code = "import sys; sys.modules['mcp'] = None; import behavioralsignals.mcp_server"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert "pip install 'behavioralsignals[mcp]'" in result.stderr


async def test_analyze_behavior_uploads_a_local_file(api):
    api.responses["wait_for_result"] = emotions(1)
    _, text = await call("analyze_behavior", source="~/call.wav")
    assert api.built == ["Behavioral"]
    assert api.calls[0] == ("upload_audio", {"file_path": HOME_FILE})
    assert api.calls[1][0] == "wait_for_result"
    assert text.startswith("pid 7 completed. Rows 1-1 of 1.")


async def test_url_upload_sends_the_file_name_without_the_query(api):
    api.responses["wait_for_result"] = emotions(1)
    url = "https://bucket.s3.amazonaws.com/calls/my%20call.wav?X-Amz-Signature=secret"
    await call("detect_deepfake", source=url, generator_detection=True)
    assert api.built == ["Deepfakes"]
    expected = {"url": url, "name": "my call.wav", "enable_generator_detection": True}
    assert api.calls[0] == ("upload_s3_presigned_url", expected)


async def test_detect_deepfake_video_uses_the_video_methods(api):
    api.responses["wait_for_video_result"] = VideoResultResponse(pid=7)
    url = "https://bucket.s3.amazonaws.com/clip.mp4?X-Amz-Signature=secret"
    await call("detect_deepfake", source="/data/clip.mp4", media="video")
    await call("detect_deepfake", source=url, media="video")
    assert [name for name, _ in api.calls] == [
        "upload_video",
        "wait_for_video_result",
        "upload_s3_presigned_video_url",
        "wait_for_video_result",
    ]
    assert api.calls[0][1] == {"file_path": "/data/clip.mp4", "enable_generator_detection": False}


@pytest.mark.parametrize(("upload_seconds", "left"), [(10.0, 35.0), (60.0, 0.0)])
async def test_upload_time_counts_toward_wait_seconds(api, monkeypatch, upload_seconds, left):
    clock = iter([0.0, upload_seconds])
    monkeypatch.setattr(mcp_server, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    api.responses["wait_for_result"] = emotions(1)
    await call("analyze_behavior", source="/data/call.wav", wait_seconds=45)
    assert api.calls[1] == ("wait_for_result", {"pid": 7, "timeout": left})


async def test_error_after_upload_keeps_the_pid(api):
    api.responses["wait_for_result"] = requests.ConnectionError("connection reset")
    is_error, text = await call("analyze_behavior", source="/data/call.wav")
    assert is_error
    assert "Uploaded as pid 7, but getting the result failed: connection reset." in text
    assert 'Retry with get_result(pid=7, analysis="behavioral").' in text


async def test_failed_job_after_upload_is_not_retried(api):
    api.responses["wait_for_result"] = RuntimeError("Process 7 did not complete: bad audio")
    is_error, text = await call("analyze_behavior", source="/data/call.wav")
    assert is_error and "Process 7 did not complete: bad audio" in text
    assert "Retry" not in text


async def test_upload_error_reaches_the_model(api):
    api.responses["upload_audio"] = FileNotFoundError("No such file: '/data/missing.wav'")
    is_error, text = await call("analyze_behavior", source="/data/missing.wav")
    assert is_error and "No such file" in text and "Uploaded" not in text


async def test_lists_the_four_tools_and_marks_read_only_ones():
    async with Client(mcp_server.server) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    assert set(tools) == {"analyze_behavior", "detect_deepfake", "get_result", "list_processes"}
    read_only = {
        name for name, tool in tools.items() if tool.annotations and tool.annotations.read_only_hint
    }
    assert read_only == {"get_result", "list_processes"}


async def test_list_processes_shows_status_names_and_failure_reasons(api):
    created = datetime(2026, 9, 20, 10, 11, 12)
    api.responses["list_processes"] = ProcessListResponse(
        processes=[
            ProcessItem(
                pid=1, name="a.wav", status=2, statusmsg="done", duration=1.5, datetime=created
            ),
            ProcessItem(pid=2, name="b.wav", status=-1, statusmsg="bad audio\n\nffmpeg log"),
            ProcessItem(pid=3, status=5),
        ]
    )
    _, text = await call(
        "list_processes", analysis="behavioral", page_size=3, start_date="2026-09-01"
    )
    assert api.calls == [
        (
            "list_processes",
            {
                "page": 0,
                "page_size": 3,
                "sort": "desc",
                "start_date": "2026-09-01",
                "end_date": None,
            },
        )
    ]
    assert text.splitlines() == [
        "pid\tname\tstatus\tduration\tcreated\treason",
        "1\ta.wav\tcompleted\t1.5\t2026-09-20 10:11:12\t",
        "2\tb.wav\tfailed\t\t\tbad audio",
        "3\t\t5\t\t\t",
        (
            'More: list_processes(analysis="behavioral", page=1, page_size=3, sort="desc", '
            'start_date="2026-09-01")'
        ),
    ]


async def test_list_processes_uses_the_video_list_for_video(api):
    api.responses["list_video_processes"] = ProcessListResponse(processes=[])
    _, text = await call("list_processes", analysis="deepfake_video")
    assert api.built == ["Deepfakes"] and api.calls[0][0] == "list_video_processes"
    assert text == "No processes found."
