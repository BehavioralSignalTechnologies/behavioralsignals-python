"""Runs the example scripts and the README snippets against a fake API.

`batch_upload_dataset.py` and `streaming_from_mic.py` are not run: they need a download, a
microphone and extra packages. CI checks them, and the others, with mypy.
"""

import re
import sys
import wave
import runpy
from types import SimpleNamespace
from pathlib import Path

import pytest
from test_client import FakeResponse, fake_requests
from test_streaming import fake_channel

from behavioralsignals.models import ProcessStatus
from behavioralsignals.generated import api_pb2 as pb


ROOT = Path(__file__).parent.parent
RESULTS = [
    {
        "task": "emotion",
        "startTime": "0.5",
        "endTime": "3.0",
        "finalLabel": "sad",
        "prediction": [{"label": "sad", "posterior": "0.9"}],
    },
    {
        "task": "positivity",
        "startTime": "0.5",
        "endTime": "3.0",
        "finalLabel": "negative",
        "prediction": [
            {"label": "negative", "posterior": "0.7"},
            {"label": "positive", "posterior": "0.1"},
        ],
    },
    {
        "task": "strength",
        "startTime": "0.5",
        "endTime": "3.0",
        "finalLabel": "weak",
        "prediction": [
            {"label": "weak", "posterior": "0.7"},
            {"label": "strong", "posterior": "0.1"},
        ],
    },
]
# The fake API gives this one answer to every request: it fits auth, process and result responses.
API_RESPONSE = {
    "pid": 1,
    "status": ProcessStatus.COMPLETED,
    "results": RESULTS,
    "audio_results": RESULTS,
    "video_results": RESULTS,
}
STREAM_RESPONSE = pb.StreamResult(
    pid=1,
    result=[pb.InferenceResult(task="emotion", final_label="sad", start_time="0", end_time="1")],
)


def write_silent_wav(path):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\0\0" * 8000)


@pytest.fixture
def fake_api(monkeypatch, tmp_path):
    """Fakes HTTP, gRPC and credentials, inside a folder with audio.wav and video.mp4."""
    monkeypatch.setenv("BEHAVIORALSIGNALS_CID", "1")
    monkeypatch.setenv("BEHAVIORALSIGNALS_API_KEY", "fake")
    # The examples need python-dotenv, which the SDK does not depend on.
    monkeypatch.setitem(sys.modules, "dotenv", SimpleNamespace(load_dotenv=lambda: None))
    fake_requests(monkeypatch, FakeResponse(body=API_RESPONSE))
    fake_channel(monkeypatch, [STREAM_RESPONSE])
    monkeypatch.chdir(tmp_path)
    write_silent_wav(tmp_path / "audio.wav")
    (tmp_path / "video.mp4").write_bytes(b"fake video")


@pytest.mark.parametrize(
    ("script", "args"),
    [
        ("batch/batch_api_polling.py", ["--file_path", "audio.wav", "--api", "behavioral"]),
        ("batch/batch_api_polling.py", ["--file_path", "audio.wav", "--api", "deepfakes"]),
        ("batch/video_deepfake_polling.py", ["--file_path", "video.mp4"]),
        ("streaming/streaming_api_file.py", ["--file_path", "audio.wav", "--api", "behavioral"]),
        ("streaming/streaming_api_file.py", ["--file_path", "audio.wav", "--api", "deepfakes"]),
    ],
)
@pytest.mark.usefixtures("fake_api")
def test_example_runs_and_saves_the_results(monkeypatch, script, args):
    monkeypatch.setattr(sys, "argv", [script, *args, "--output", "out.json"])
    runpy.run_path(str(ROOT / "examples" / script), run_name="__main__")
    assert "sad" in Path("out.json").read_text()


@pytest.mark.usefixtures("fake_api")
def test_readme_python_snippets_run_in_order():
    # Later snippets use names from earlier ones, as a reader would, so they share a namespace.
    snippets = re.findall(r"(?ms)^```python\n(.*?)^```", (ROOT / "README.md").read_text())
    assert snippets
    namespace = {}
    for snippet in snippets:
        exec(snippet, namespace)
