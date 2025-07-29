"""A simple example script demonstrating how to use the Behavioral Signals API client.
This script uses the batch API. The batch API works as follows:
    1. Submit your audio and retrieve a process ID (pid).
    2. After a short delay, retrieve the results using this pid.

In this example, we implement a simple polling mechanism to check the status of the process.
Script adapted by: https://github.com/BehavioralSignalTechnologies/oliver_api/blob/main/send_data_to_api.py
"""

import os
import json
import time
import argparse

from dotenv import load_dotenv

from behavioralsignals import Client


def parse_args():
    parser = argparse.ArgumentParser(description="Behavioral Signals API Client Example")
    parser.add_argument(
        "--file_path", type=str, required=True, help="Path to the audio file to send"
    )
    parser.add_argument(
        "--output", type=str, default="output.json", help="Path to save the output JSON file"
    )
    parser.add_argument(
        "--api", type=str, default="behavioral", choices=["behavioral", "deepfakes"], help="API to use for streaming"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    file_path, output = args.file_path, args.output

    # Step 1. Initialize the client with your user ID and API key
    load_dotenv()
    base_client = Client(user_id=os.getenv("USER_ID"), api_key=os.getenv("API_KEY"))

    # Step 2. Send the audio file for processing
    if args.api == "behavioral":
        client = base_client.behavioral
    elif args.api == "deepfakes":
        client = base_client.deepfakes
    upload_response = client.upload_audio(file_path=file_path)
    pid = upload_response.pid
    print(f"Sent audio for processing! Process ID (pid): {pid}")

    # Step 3. Poll the API to check the status of the process
    last_status = None
    while True:
        process = client.get_process(pid=pid)
        status = process.statusmsg

        if process.is_completed:
            if last_status != process.statusmsg:
                print("Processing complete!")
            break
        elif process.is_processing:
            if last_status != process.statusmsg:
                print("Processing audio...")
        elif process.is_pending:
            if last_status != process.statusmsg:
                print("API is busy, waiting...")
        else:
            if last_status != process.statusmsg:
                print(f"Unexpected status: {process.statusmsg}")
            break

        last_status = status
        # Wait before polling again
        time.sleep(1.0)

    # Step 4. Retrieve the results if processing is complete and save to output file
    if process.is_completed:
        result = client.get_result(pid=pid)
        result_dict = result.model_dump()

        with open(output, "w") as f:
            json.dump(result_dict, f, indent=4)
        print(f"Results saved to {output}")
