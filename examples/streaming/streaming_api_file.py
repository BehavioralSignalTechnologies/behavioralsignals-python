import os
import argparse

from pydub import AudioSegment
from dotenv import load_dotenv
from pydub.utils import make_chunks

from behavioralsignals import Client


load_dotenv()

CHUNK_SIZE = 0.25  # chunk size in milliseconds
SAMPLE_RATE = 16000


def parse_args():
    parser = argparse.ArgumentParser(description="Behavioral Signals API Client Example")
    parser.add_argument("--file_path", type=str, required=True, help="Path to the audio file to send")
    parser.add_argument("--output", type=str, default="output.json", help="Path to save the output JSON file")
    return parser.parse_args()


args = parse_args()
file_path, output = args.file_path, args.output

# Step 1. Initialize the client with your user ID and API key
client = Client(user_id=os.getenv("USER_ID"), api_key=os.getenv("API_KEY"))

# Step 2. Read the audio file, and wrap it inside an iterator of chunks
snd = AudioSegment.from_file(file_path, format="wav")
snd = snd.set_frame_rate(SAMPLE_RATE)  # Ensure the audio is at 16kHz
snd = snd.set_channels(1)  # Ensure the audio is mono
snd = snd.set_sample_width(2)  # Ensure the audio is in 16-bit

chunks_list = make_chunks(snd, CHUNK_SIZE * 1000)
audio_stream = iter([chunk.raw_data for chunk in chunks_list])
options_dict = {"sample_rate": SAMPLE_RATE}
for resp in client.stream_audio(audio_stream, streaming_options=options_dict):
    print(type(resp))
