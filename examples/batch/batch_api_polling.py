"""A simple example script demonstrating how to use the Behavioral Signals API client.
This script uses the batch API. The batch API works as follows:
    1. Submit your audio and retrieve a process ID (pid).
    2. After a short delay, retrieve the results using this pid.

In this example, we implement a simple polling mechanism to check the status of the process.
Script adapted by: https://github.com/BehavioralSignalTechnologies/oliver_api/blob/main/send_data_to_api.py
"""

import os
import time
import argparse

from dotenv import load_dotenv

from behavioralsignals import Client


def parse_args():
    parser = argparse.ArgumentParser(description="Behavioral Signals API Client Example")
    parser.add_argument("--file_path", type=str, required=True, help="Path to the audio file to send")
    parser.add_argument("--output", type=str, default="output.json", help="Path to save the output JSON file")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    file_path, output = args.file_path, args.output

    # Step 1. Initialize the client with your user ID and API key
    load_dotenv()
    client = Client(user_id=os.getenv("USER_ID"), api_key=os.getenv("API_KEY"))

    # Step 2. Send the audio file for processing
    send_response = client.send_audio(file_path=file_path)
    pid = send_response.get("pid")
    print(f"Sent audio for processing! Process ID (pid): {pid}")

    # Step 3. Poll the API to check the status of the process
    done = False
    while True:
        pid_status = client.check_process_status(pid=pid)["status"]
        if pid_status == 2:
            done = True
            print("Processing complete!")
            break
        elif pid_status == 1:
            print("Processing audio...")
        elif pid_status == 0:
            print("API is busy, waiting...")
        else:
            print(f"Unexpected status: {pid_status}")
            break
        time.sleep(1.0)

    # Step 4. Retrieve the results if processing is complete and save to output file
    if done:
        result = client.get_result(pid=pid)
        with open(output, "w") as f:
            import json

            json.dump(result, f, indent=4)
        print(f"Results saved to {output}")
