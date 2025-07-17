# Streaming API Examples

This directory showcases how the Behavioral Signals Python SDK can be used to interact with the streaming API.
The examples demonstrate how to send audio data in real-time and receive behavioral analysis results.

Before running the scripts, ensure you have set up your environment correctly (note: we use [Astral's uv](https://docs.astral.sh/uv/) as the default package manager):
```bash
uv venv -p python3.10 venv
source venv/bin/activate

uv pip install behavioralsignals
```

## 📁 Stream from file

Use `streaming_api_file.py` to send audio data from a file to the Behavioral Signals API in real-time.
```bash
python streaming_api_file.py --file audio.wav
```
The results will be printed to the console as they are processed.


## 🎤 Record from microphone

You can use the streaming_api_microphone.py script to capture audio directly from your microphone and stream it to the Behavioral Signals API in real time.
This is a common use case when integrating with audio streaming APIs for live analysis or feedback.

First, make sure you install some additional dependencies required for audio capture and live display:
```bash
uv pip install sounddevice numpy rich
```

Then, run the script and start speaking into your microphone:
```bash
python streaming_api_microphone.py
```
