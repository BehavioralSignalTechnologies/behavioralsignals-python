from collections.abc import Iterable, Iterator

from pydub import AudioSegment
from pydub.utils import make_chunks

from .models import ResultItem


def make_audio_stream(file_path: str, chunk_size: float = 0.25) -> tuple[Iterator[bytes], int]:
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


def print_results(items: Iterable[ResultItem] | None) -> None:
    """Print one line per result: start time, end time, task, top label and its probability.

    Continuous tasks (e.g. intensity) have no label, so their score is printed instead.
    Rows without a prediction, label or score (e.g. the features row, which carries embeddings) are skipped.

    Args:
        items (Iterable[ResultItem] | None): Result items, e.g. `result.results`.
    """
    for item in items or []:
        if not item.prediction:
            continue
        top = item.prediction[0]
        label = item.finalLabel or top.score
        if not label:
            continue
        confidence = f" ({float(top.posterior):.1%})" if top.posterior else ""
        print(f"{item.st} {item.et} {item.task} {label}{confidence}")
