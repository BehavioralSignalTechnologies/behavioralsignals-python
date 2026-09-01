"""Example script demonstrating video deepfake detection via the batch API.

The batch API works as follows:
    1. Submit your video and retrieve a process ID (pid).
    2. Poll the process until it completes.
    3. Retrieve the results using this pid. The video result response contains two
       separate lists: `audio_results` (deepfake detection on the audio track) and
       `video_results` (deepfake detection on the video frames).

Video deepfake detection is currently available in batch mode only.
"""

import os
import json
import time
import argparse

from dotenv import load_dotenv

from behavioralsignals import Client


def parse_args():
    parser = argparse.ArgumentParser(description="Video Deepfake Detection Example")
    parser.add_argument(
        "--file_path", type=str, required=True, help="Path to the video file to send"
    )
    parser.add_argument(
        "--output", type=str, default="video_output.json", help="Path to save the output JSON file"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    file_path, output = args.file_path, args.output

    # Step 1. Initialize the client with your client ID and API key.
    load_dotenv()
    client = Client(cid=os.getenv("CID"), api_key=os.getenv("API_KEY")).deepfakes

    # Step 2. Send the video file for processing
    upload_response = client.upload_video(file_path=file_path)
    pid = upload_response.pid
    print(f"Sent video for processing! Process ID (pid): {pid}")

    # Step 3. Poll the API to check the status of the process
    last_status = None
    while True:
        process = client.get_video_process(pid=pid)
        status = process.statusmsg

        if process.is_completed:
            if last_status != process.statusmsg:
                print("Processing complete!")
            break
        elif process.is_processing:
            if last_status != process.statusmsg:
                print("Processing video...")
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
        result = client.get_video_result(pid=pid)
        result_dict = result.model_dump()

        n_audio = len(result.audio_results or [])
        n_video = len(result.video_results or [])
        print(f"Got {n_audio} audio result(s) and {n_video} video result(s).")

        with open(output, "w") as f:
            json.dump(result_dict, f, indent=4)
        print(f"Results saved to {output}")
