from typing import Tuple, Iterator

from pydub import AudioSegment
from pydub.utils import make_chunks


def make_audio_stream(file_path: str, chunk_size: float = 0.25) -> Tuple[Iterator[bytes], int]:
    """Create an audio stream from a file, yielding chunks of raw audio data.

    Args:
        file_path (str): Path to the audio file.
        chunk_size (float): Size of each chunk in seconds. Default is 0.25 seconds.

    Returns:
        Iterator[bytes]: An iterator yielding raw audio data chunks.
        int: Sample rate of the audio.
    """

    snd = AudioSegment.from_file(file_path)
    snd = snd.set_sample_width(2)
    snd = snd.set_channels(1)

    chunks = iter([chunk.raw_data for chunk in make_chunks(snd, chunk_size * 1000)])
    return chunks, snd.frame_rate
