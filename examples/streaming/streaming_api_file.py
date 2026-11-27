import json
import math
import argparse
from array import array
from collections.abc import Iterator

from dotenv import load_dotenv

from behavioralsignals import END_OF_TURN, Client, EndOfTurn, StreamingOptions
from behavioralsignals.utils import print_results, make_audio_stream


CHUNK_SECONDS = 0.25
# A chunk quieter than this counts as silence. It stands in for a real turn detector.
SILENCE_DBFS = -40.0


def parse_args():
    parser = argparse.ArgumentParser(description="Behavioral Signals API Client Example")
    parser.add_argument(
        "--file_path", type=str, required=True, help="Path to the audio file to send"
    )
    parser.add_argument(
        "--output", type=str, default="output.json", help="Path to save the output JSON file"
    )
    parser.add_argument(
        "--api",
        type=str,
        default="behavioral",
        choices=["behavioral", "deepfakes"],
        help="API to use for streaming",
    )
    parser.add_argument(
        "--response_level",
        type=str,
        default="segment",
        choices=["segment", "utterance", "all"],
        help="Level of response granularity",
    )

    parser.add_argument(
        "--focus",
        type=str,
        help="Comma-separated labels to focus on, e.g. angry,low_confidence (behavioral only)",
    )
    parser.add_argument(
        "--sensitivity",
        type=str,
        default="default",
        choices=["low", "default", "high"],
        help="Focus sensitivity",
    )
    parser.add_argument(
        "--continuous",
        type=str,
        help="Comma-separated continuous values, e.g. valence,arousal (behavioral only)",
    )
    parser.add_argument(
        "--end_of_turn_after",
        type=float,
        help="Send END_OF_TURN after this many seconds of silence that follows speech",
    )

    return parser.parse_args()


def is_silent(chunk: bytes) -> bool:
    """True if a chunk of 16-bit audio is quieter than SILENCE_DBFS."""
    samples = array("h", chunk)
    rms = math.sqrt(sum(s * s for s in samples) / max(len(samples), 1))
    return 20 * math.log10(max(rms, 1) / 32768) < SILENCE_DBFS


def with_end_of_turn(
    chunks: Iterator[bytes], silence_seconds: float
) -> Iterator[bytes | EndOfTurn]:
    """Yields the chunks, and END_OF_TURN once per pause of `silence_seconds` after speech."""
    silent_chunks, in_turn = 0, False
    for chunk in chunks:
        yield chunk
        silent_chunks = silent_chunks + 1 if is_silent(chunk) else 0
        in_turn = in_turn or silent_chunks == 0
        if in_turn and silent_chunks * CHUNK_SECONDS >= silence_seconds:
            yield END_OF_TURN
            in_turn = False


if __name__ == "__main__":
    args = parse_args()
    file_path, output = args.file_path, args.output

    # Step 1. Initialize the client with your user ID and API key
    load_dotenv()
    client = Client()

    # Step 2. Read the audio file, and wrap it inside an iterator of chunks
    chunks, sample_rate = make_audio_stream(file_path, chunk_size=CHUNK_SECONDS)
    # Optional: mark the end of each turn, here after a pause (a voice agent uses its turn detector)
    audio_stream: Iterator[bytes | EndOfTurn] = chunks
    if args.end_of_turn_after:
        audio_stream = with_end_of_turn(chunks, args.end_of_turn_after)
    options = StreamingOptions(
        sample_rate=sample_rate,
        encoding="LINEAR_PCM",
        level=args.response_level,
        focus=args.focus.split(",") if args.focus and args.api == "behavioral" else None,
        sensitivity=args.sensitivity,
        continuous=args.continuous.split(",")
        if args.continuous and args.api == "behavioral"
        else None,
    )

    if args.api == "behavioral":
        responses = client.behavioral.stream_audio(audio_stream=audio_stream, options=options)
    else:
        responses = client.deepfakes.stream_audio(audio_stream=audio_stream, options=options)

    output_data = []
    for resp in responses:
        print_results(resp.results)
        resp_data = resp.model_dump()
        output_data.append(resp_data)

    with open(output, "w") as f:
        json.dump(output_data, f, indent=4)

    print(f"Results saved to {output}")
