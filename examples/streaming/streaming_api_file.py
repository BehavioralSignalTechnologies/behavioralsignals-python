import os
import argparse

from dotenv import load_dotenv

from behavioralsignals import Client, StreamingOptions
from behavioralsignals.utils import make_audio_stream


def parse_args():
    parser = argparse.ArgumentParser(description="Behavioral Signals API Client Example")
    parser.add_argument(
        "--file_path", type=str, required=True, help="Path to the audio file to send"
    )
    parser.add_argument(
        "--output", type=str, default="output.json", help="Path to save the output JSON file"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    file_path, output = args.file_path, args.output

    # Step 1. Initialize the client with your user ID and API key
    load_dotenv()
    client = Client(user_id=os.getenv("USER_ID"), api_key=os.getenv("API_KEY"))

    # Step 2. Read the audio file, and wrap it inside an iterator of chunks
    audio_stream, sample_rate = make_audio_stream(file_path, chunk_size=0.25)
    options = StreamingOptions(sample_rate=sample_rate)
    for resp in client.stream_audio(audio_stream, options=options):
        print(resp)
