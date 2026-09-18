import wave

import pytest

from behavioralsignals.utils import make_audio_stream


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
