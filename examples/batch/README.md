# Batch Mode Examples

This directory illustrates how a user would interact with the batch mode of Behavioral Signals API through the Python SDK.
There are two main examples, which are displayed below.

Before running the scripts, ensure you have set up your environment correctly (note: we use [Astral's uv](https://docs.astral.sh/uv/) as the default package manager):
```bash
uv venv -p python3.10 venv
source venv/bin/activate

uv pip install behavioralsignals python-dotenv
```

For convenience, all of our examples read your API credentials from the environment variables `BEHAVIORALSIGNALS_CID` and `BEHAVIORALSIGNALS_API_KEY`.
You can either set them in your shell:
```bash
export BEHAVIORALSIGNALS_CID=your_cid
export BEHAVIORALSIGNALS_API_KEY=your_api_key
```

or create a `.env` file in the same directory as the scripts with the following content, which will be automatically loaded by the examples:
```bash
BEHAVIORALSIGNALS_CID=your_cid
BEHAVIORALSIGNALS_API_KEY=your_api_key
```

## Submit file

The `batch_api_polling.py` is a simple script that submits and audio file to the Behavioral Signals API and then waits for the results with `wait_for_result`.
```bash
python batch_api_polling.py --file_path audio.wav --output audio_results.json --api behavioral
```
With the `--api` argument you can specify which API to use (either `behavioral` or `deepfakes`). You can also set the `--embeddings` flag to include speaker and behavioral/deepfake embeddings in the output.

The results are saved to `audio_results.json` file once they are ready.

## Find the moments that stand out, in one command

The `focus_results.py` script takes audio files or a folder and the outputs you care about, uploads the audio, waits for the results and prints the moments where those outputs reach their threshold, including those the API labeled `neutral`:
```bash
python focus_results.py call.wav --outputs angry hesitation
```
It saves the API results to `call_results.json` and the flagged moments to `call_focus.csv`. Give it several files or a folder to do many calls at once (`python focus_results.py calls/ --outputs angry`); it also saves `focus_summary.csv` (one row per call) and `focus_all.csv` (every flagged moment) next to them, and prints one line per call (add `--details` to print every flagged moment too). To run again without uploading again, give it the saved results, with the same or other outputs:
```bash
python focus_results.py call_results.json --outputs negative hesitation
```
The SDK also computes two outputs of its own: `negative_tone` (a negative voice, from the emotion and positivity probabilities) and `negative_words` (negative content in the transcript, from a text model). See the [main README](../../README.md#computed-outputs). `negative_words` needs the `words` extra first (`pip install "behavioralsignals[words]"`):
```bash
python focus_results.py calls/ --outputs negative_tone negative_words
```
With either of them, it also saves the results with their rows added to `call_results_focus.json`.

To see the results in your browser instead, run the focus viewer (from the repository root):
```bash
uv run --extra words --with streamlit streamlit run examples/batch/focus_app.py
```
Enter an audio file or folder, pick outputs and move the thresholds. Audio with saved results is not uploaded again; the rest is uploaded when you click the button. Subfolders (for example two sets of calls you want to compare) are shown side by side. It has three tabs: an overview with flags per group and per call, threshold plots (how the scores are spread and how many utterances and calls each threshold flags), and a player where you click an utterance to hear it and see every API output for it.

## Video deepfake detection

The `video_deepfake_polling.py` script submits a video file to the Deepfakes API for video deepfake detection and waits for the results with `wait_for_video_result`.
```bash
python video_deepfake_polling.py --file_path video.mp4 --output video_results.json
```

Video deepfake detection is available in batch mode only. Unlike the audio results, the video result response splits the results into two lists — `audio_results` (deepfake detection on the audio track) and `video_results` (deepfake detection on the video frames) — and both are saved to the output JSON file.

## Evaluation from HuggingFace 🤗 Dataset

We also provide `batch_upload_dataset.py`, which demonstrates how to upload a dataset from HuggingFace 🤗 and evaluate it using the Behavioral Signals API.

For the purposes of this example, we have uploaded a sample dataset of 22 audio files to our [HuggingFace repository](https://huggingface.co/datasets/behavioralsignals/deepfake-detection-demo).
The dataset contains 1 spoofed ("deepfake") and 1 genuine ("bonafide") audio file for 11 different languages.

First, make sure you install some additional dependencies required for dataset handling:
```bash
uv pip install "datasets<4.0.0" soundfile librosa tqdm
```

Then, run the script to upload the dataset and evaluate it:
```bash
python batch_upload_dataset.py
```

The script will upload the dataset to the Behavioral Signals API and evaluate the generated results, printing the classification confusion matrix to the console.