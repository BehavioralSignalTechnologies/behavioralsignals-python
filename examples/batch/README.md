# Batch Mode Examples

This directory illustrates how a user would interact with the batch mode of Behavioral Signals API through the Python SDK.
There are two main examples, which are displayed below.

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

## Submit file

The `batch_api_polling.py` is a simple script that submits and audio file to the Behavioral Signals API and then polls for the results until they are ready.
```bash
python batch_api_polling.py --file_path audio.wav --output audio_results.json --api behavioral
```
With the `--api` argument you can specify which API to use (either `behavioral` or `deepfakes`). You can also set the `--embeddings` flag to include speaker and behavioral/deepfake embeddings in the output.

The results are saved to `audio_results.json` file once they are ready.

## Evaluation from HuggingFace 🤗 Dataset

We also provide `batch_upload_dataset.py`, which demonstrates how to upload a dataset from HuggingFace 🤗 and evaluate it using the Behavioral Signals API.

For the purposes of this example, we have uploaded a sample dataset of 22 audio files to our [HuggingFace repository](https://huggingface.co/datasets/behavioralsignals/deepfake-detection-demo).
The dataset contains 1 spoofed ("deepfake") and 1 genuine ("bonafide") audio file for 11 different languages.

First, make sure you install some additional dependencies required for dataset handling:
```bash
uv pip install "datasets<4.0.0" soundfile librosa tqdm
```

Then, run the script aset and evaluate it:
```bash
python batch_upload_dataset.py
```

The script will upload the dataset to the Behavioral Signals API and evaluate the generated results, printing the classification confusion matrix to the console.