"""A simple example script demonstrating how to use the Behavioral Signals API client.
This script uses the batch API. The batch API works as follows:
    1. Submit your audio and retrieve a process ID (pid).
    2. Wait for processing to finish and retrieve the results using this pid.

In this example, `wait_for_result` checks the status of the process until it is done.
Script adapted by: https://github.com/BehavioralSignalTechnologies/oliver_api/blob/main/send_data_to_api.py
"""

import json
import argparse

from dotenv import load_dotenv

from behavioralsignals import Client, Deepfakes, Behavioral


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
        help="API to use for processing",
    )
    parser.add_argument(
        "--embeddings",
        action="store_true",
        help="Whether to include embeddings in the output",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    file_path, output = args.file_path, args.output

    # Step 1. Initialize the client with your user ID and API key
    load_dotenv()
    base_client = Client()

    # Step 2. Send the audio file for processing
    if args.api == "behavioral":
        client: Behavioral | Deepfakes = base_client.behavioral
    else:
        client = base_client.deepfakes
    upload_response = client.upload_audio(file_path=file_path, embeddings=args.embeddings)
    pid = upload_response.pid
    print(f"Sent audio for processing! Process ID (pid): {pid}")

    # Step 3. Wait until processing is complete and get the results
    print("Processing audio...")
    result = client.wait_for_result(pid=pid)
    print("Processing complete!")

    # Step 4. Save the results to the output file
    with open(output, "w") as f:
        json.dump(result.model_dump(), f, indent=4)
    print(f"Results saved to {output}")
