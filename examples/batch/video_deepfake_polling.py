"""Example script demonstrating video deepfake detection via the batch API.

The batch API works as follows:
    1. Submit your video and retrieve a process ID (pid).
    2. Wait for the process to complete with `wait_for_video_result`.
    3. Retrieve the results using this pid. The video result response contains two
       separate lists: `audio_results` (deepfake detection on the audio track) and
       `video_results` (deepfake detection on the video frames).

Video deepfake detection is currently available in batch mode only.
"""

import json
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
    client = Client().deepfakes

    # Step 2. Send the video file for processing
    upload_response = client.upload_video(file_path=file_path)
    pid = upload_response.pid
    print(f"Sent video for processing! Process ID (pid): {pid}")

    # Step 3. Wait until processing is complete and get the results
    print("Processing video...")
    result = client.wait_for_video_result(pid=pid)
    print("Processing complete!")

    # Step 4. Save the results to the output file
    n_audio = len(result.audio_results or [])
    n_video = len(result.video_results or [])
    print(f"Got {n_audio} audio result(s) and {n_video} video result(s).")

    with open(output, "w") as f:
        json.dump(result.model_dump(), f, indent=4)
    print(f"Results saved to {output}")
