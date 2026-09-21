import sys
import subprocess

import pytest
import requests
from mcp import Client

from behavioralsignals import BehavioralSignalsError, mcp_server
from behavioralsignals.models import (
    ResultItem,
    ProcessItem,
    ResultResponse,
    ModelPredictions,
    VideoResultResponse,
)


pytestmark = pytest.mark.anyio


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
