# Streaming API Examples

This directory showcases how the Behavioral Signals Python SDK can be used to interact with the streaming API.
The examples demonstrate how to send audio data in real-time and receive behavioral analysis results.

Before running the scripts, ensure you have set up your environment correctly (note: we use [Astral's uv](https://docs.astral.sh/uv/) as the default package manager):
```bash
uv venv -p python3.10 venv
source venv/bin/activate

uv pip install behavioralsignals python-dotenv
```

For convenience, all of our examples read your API credentials from the environment variables `CID` and `API_KEY`.
You can either set them in your shell:
```bash
export CID=your_cid
export API_KEY=your_api_key
```

or create a `.env` file in the same directory as the scripts with the following content, which will be automatically loaded by the examples:
```bash
CID=your_cid
API_KEY=your_api_key
```

## 🎤 Record from microphone

You can use the streaming_api_microphone.py script to capture audio directly from your microphone and stream it to the Behavioral Signals API in real time.
This is a common use case when integrating with audio streaming APIs for live analysis or feedback.

First, make sure you install some additional dependencies required for audio capture and live display:
```bash
uv pip install sounddevice numpy rich
```

Then, run the script and start speaking into your microphone. The results will be displayed in a live table format, showing the analysis of your speech in real-time.

```bash
python streaming_from_mic.py --api behavioral --response_level all
```

* The `--api` argument specifies which API to use (either `behavioral` or `deepfakes`).
* The `--response_level` argument controls the level of response granularity. Options include `segment`, `utterance` and `all`:
    - `segment`: Provides segment-level results, i.e. interim results for 2-second segments of continuous speech
    - `utterance`: Provides utterance-level results, i.e. results for complete utterances. Conceptually, an utterance is made up of one or more segments (though with `--response-level utterances`, only the uttterance-level results are returned).
    - `all`: Provides all available results for each utterance, including segment-level results and utterance-level.


## 📁 Stream from file

Use `streaming_api_file.py` to send audio data from a file to the Behavioral Signals API in real-time. This has limited usability but we include it for completeness.
```bash
python streaming_api_file.py --file audio.wav --output results.json --api behavioral --response_level all
```
The results will be printed to the console in raw format as they are processed, and will be also saved to a file named `results.json`.
