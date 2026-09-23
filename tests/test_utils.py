import sys
import wave
import subprocess

import pytest

from behavioralsignals.utils import print_results, make_audio_stream
from behavioralsignals.models import ResultItem


@pytest.fixture
def wav_file(tmp_path):
    """One second of silence: 16 kHz, mono, 16-bit."""
    path = tmp_path / "audio.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 16000)
    return str(path)


def test_make_audio_stream_splits_the_audio_into_chunks(wav_file):
    chunks, sample_rate = make_audio_stream(wav_file, chunk_size=0.25)
    chunks = list(chunks)
    assert sample_rate == 16000
    assert len(chunks) == 4
    assert {len(chunk) for chunk in chunks} == {8000}


def _item(task, prediction, final_label=None):
    return ResultItem(
        task=task,
        startTime="0.487",
        endTime="3.001",
        prediction=prediction,
        finalLabel=final_label,
    )


def test_print_results_prints_one_line_per_result(capsys):
    print_results(
        [
            _item("emotion", [{"label": "sad", "posterior": "0.706"}], "sad"),
            _item("intensity", [{"score": "0.0873"}]),
            _item("diarization", [{"label": "SPEAKER_00"}], "SPEAKER_00"),
            _item("features", [{"label": None}]),
            _item("gender", None),
            _item("language", None, "en"),
            _item("asr", None, " Hello there."),
        ]
    )
    assert capsys.readouterr().out == (
        "0.487 3.001 emotion sad (70.6%)\n"
        "0.487 3.001 intensity 0.0873\n"
        "0.487 3.001 diarization SPEAKER_00\n"
        "0.487 3.001 language en\n"
        "0.487 3.001 asr Hello there.\n"
    )


def test_print_results_accepts_none(capsys):
    print_results(None)
    assert capsys.readouterr().out == ""


def test_importing_utils_does_not_load_pydub():
    """pydub warns when ffmpeg is missing, so only make_audio_stream() should load it."""
    code = "import sys, behavioralsignals.utils; print('pydub' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
