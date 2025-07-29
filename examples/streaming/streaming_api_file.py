import os
import json
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
    parser.add_argument(
        "--api", type=str, default="behavioral", choices=["behavioral", "streaming"], help="API to use for streaming"
    )
    parser.add_argument(
        "--response_level",
        type=str,
        default="segments",
        choices=["segments", "utterances", "all"],
        help="Level of response granularity",
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
    options = StreamingOptions(sample_rate=sample_rate, encoding="LINEAR_PCM")

    if args.api == "behavioral":
        responses = client.behavioral.stream_audio(audio_stream=audio_stream, options=options)
    else:
        responses = client.deepfakes.stream_audio(audio_stream=audio_stream, options=options)

    output_data = []
    for resp in responses:
        print(resp)
        resp_data = resp.model_dump()
        output_data.append(resp_data)

    with open(output, "w") as f:
        json.dump(output_data, f, indent=4)

    print(f"Results saved to {output}")