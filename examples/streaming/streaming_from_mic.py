import os
import time
import argparse
import threading
from queue import Queue

import sounddevice as sd
from dotenv import load_dotenv
from rich.live import Live
from rich.table import Table
from rich.console import Console

from behavioralsignals import Client, StreamingOptions


SAMPLE_RATE = 16000  # Sample rate in Hz
CHANNELS = 1  # Mono audio
CHUNK_DURATION_SEC = 0.25  # Duration of each chunk in seconds
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_SEC)


def make_table(resp):
    table = Table(title=f"cid={resp.cid}  pid={resp.pid}  msg={resp.message_id}")
    table.add_column("Task", no_wrap=True)
    table.add_column("Label")
    table.add_column("Score", justify="right")

    # Add timestamps row if available
    if resp.results:
        st, et = resp.results[0].st, resp.results[0].et
        table.add_row("Timestamps", f"{st} → {et} (s)", "")

    for res in resp.results:
        scores = []
        for p in res.prediction:
            try:
                score = float(p.posterior or 0.0)
            except ValueError:
                score = 0.0
            scores.append((p.label, score))

        if scores:
            best_label, best_score = max(scores, key=lambda x: x[1])
        else:
            best_label, best_score = "–", 0.0

        if best_score >= 0.8:
            color = "bright_green"
        elif best_score >= 0.5:
            color = "bright_yellow"
        else:
            color = "bright_red"

        score_cell = f"[bold {color}]{best_score:.2f}[/]"

        table.add_row(res.task, best_label, score_cell)

    return table


def audio_capture(q: Queue):
    def callback(indata, frames, time_info, status):
        if status:
            print(f"⚠️ Audio warning: {status}")
        q.put(indata.copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=CHUNK_SIZE,
        callback=callback,
    ):
        print(f"🎤 Recording @ {SAMPLE_RATE}Hz, chunk={CHUNK_DURATION_SEC}s. Ctrl+C to stop.")
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping recording.")
            q.put(None)


def audio_stream_from_queue(q: Queue):
    while True:
        chunk = q.get()
        if chunk is None:
            break
        yield chunk.tobytes()


def parse_args():
    parser = argparse.ArgumentParser(description="Behavioral Signals Streaming Example")
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
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Step 1. Initialize the client with your user ID and API key
    load_dotenv()
    client = Client(cid=os.getenv("CID"), api_key=os.getenv("API_KEY"))

    # Step 2. Start audio capture in a separate thread, and push audio chunks to a queue
    chunks_queue = Queue()
    threading.Thread(target=audio_capture, args=(chunks_queue,), daemon=True).start()

    # Step 3. Send the audio stream for processing
    audio_stream = audio_stream_from_queue(chunks_queue)
    options = StreamingOptions(
        sample_rate=SAMPLE_RATE, encoding="LINEAR_PCM", level=args.response_level
    )

    if args.api == "behavioral":
        responses = client.behavioral.stream_audio(audio_stream=audio_stream, options=options)
    else:
        responses = client.deepfakes.stream_audio(audio_stream=audio_stream, options=options)

    # Step 4. Display the results in a live table
    console = Console()
    with Live(console=console, refresh_per_second=4) as live:
        for resp in responses:
            live.update(make_table(resp))
