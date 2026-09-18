# Behavioral Signals API Python SDK

<p align="center">
  <img src="https://raw.githubusercontent.com/BehavioralSignalTechnologies/behavioralsignals-python/main/assets/logo.png" alt="Behavioral Signal Technologies"/>
</p>

<div align="center">



[![Discord](https://badgen.net/discord/members/fxjRrbMH3Q/?color=8978cc&icon=discord)](https://discord.com/invite/fxjRrbMH3Q)
[![Twitter](https://badgen.net/badge/b/behavioralsignals/icon?icon=twitter&label&color=black)](https://x.com/behaviorsignals)
[![readme.io](https://badgen.net/badge/readme.io/Documentation/?color=black)](https://behavioralsignals.readme.io/)
[![PyPI](https://badgen.net/pypi/v/behavioralsignals)](https://pypi.org/project/behavioralsignals/)
[![Python](https://badgen.net/pypi/python/behavioralsignals)](https://pypi.org/project/behavioralsignals/)
[![License](https://badgen.net/badge/license/Apache-2.0/blue)](https://github.com/BehavioralSignalTechnologies/behavioralsignals-python/blob/main/LICENSE)

</div>

Python SDK for the Behavioral Signals API. Behavioral Signals builds AI solutions that understand human behavior through voice and detect deepfake content in audio.
Our API enables developers to integrate behavioral analysis into their applications, both in batch and streaming modes.
See the [API documentation](https://behavioralsignals.readme.io/) for details. It is also available as [llms.txt](https://behavioralsignals.readme.io/llms.txt) for AI coding assistants.


## Table of Contents
* [Behavioral Signals API Python SDK](#behavioral-signals-api-python-sdk)
  * [Features](#features)
  * [Requirements](#requirements)
  * [API Key Setup](#api-key-setup)
  * [SDK Installation](#sdk-installation)
  * [SDK Example Usage](#sdk-example-usage)
    * [Behavioral API Batch Mode](#behavioral-api-batch-mode)
    * [Behavioral API Streaming Mode](#behavioral-api-streaming-mode)
    * [Deepfakes API Batch Mode](#deepfakes-api-batch-mode)
    * [Deepfakes API Streaming Mode](#deepfakes-api-streaming-mode)
  * [Available Methods](#available-methods)
  * [Error Handling](#error-handling)

## Features

- **Behavioral Analysis API** : Analyze human behavior in both batch (offline) and streaming (online) modes.

- **Deepfake Detection API**: Detect synthetic or manipulated speech using advanced deepfake detection models.  
  - Supports batch (offline) and streaming (online) modes  
  - Compatible with a wide range of spoken languages

- **Core Speech Attributes (Batch Only)**: Extract foundational conversational metadata from both APIs:  
  - Automatic Speech Recognition (ASR)  
  - Speaker Diarization  
  - Language Identification

## Requirements

* `Python3.10+`,
* `ffmpeg`,
* Python dependencies as specified in `pyproject.toml`


## API Key Setup

To use the Behavioral Signals API, you need to create an account and obtain an API key from the [Behavioral Signals portal](https://portal.behavioralsignals.com/).

You can pass your client ID (CID) and API key to `Client(YOUR_CID, YOUR_API_KEY)`, or set them as environment variables and call `Client()`:

```bash
export BEHAVIORALSIGNALS_CID=your_cid
export BEHAVIORALSIGNALS_API_KEY=your_api_key
```

## SDK Installation

```bash
pip install behavioralsignals
```

## SDK Example Usage

After obtaining your API key, you can use the SDK to interact with the Behavioral Signals APIs.
We currently provide two main APIs:

* the **Behavioral API** for analyzing human behavior through voice, and
* the **Deepfakes API** for detecting deepfake audio content in human speech.

Both APIs support batch and streaming modes, allowing you to send audio files or streams for analysis and receive results after processing and in real-time, respectively.
You can also find more detailed examples for both [batch](https://github.com/BehavioralSignalTechnologies/behavioralsignals-python/blob/main/examples/batch/README.md) and [streaming](https://github.com/BehavioralSignalTechnologies/behavioralsignals-python/blob/main/examples/streaming/README.md) in the `examples/` directory.

### Behavioral API Batch Mode

In batch mode, you can send audio files to the Behavioral Signals API for analysis. The API will return a unique process ID (PID) that you can use to retrieve the results later.
`wait_for_result` checks the process status until processing is complete, then returns the results (available since version 0.6.0).
Pass `timeout` in seconds to stop waiting after that long; it raises `TimeoutError` if processing has not finished.

```python
from behavioralsignals import Client

client = Client(YOUR_CID, YOUR_API_KEY)

response = client.behavioral.upload_audio(file_path="audio.wav")
output = client.behavioral.wait_for_result(pid=response.pid, timeout=600)

for item in output.results or []:
    top = item.prediction[0]
    label = item.finalLabel or top.score  # continuous tasks (e.g. intensity) have no label
    confidence = f" ({float(top.posterior):.1%})" if top.posterior else ""
    print(f"{item.st} {item.et} {item.task} {label}{confidence}")
```

Each result row has the start and end time in seconds, the task, and the top label with its probability.
Continuous tasks such as `intensity` have no label, only a score, and `asr` and `diarization` have a label without a probability.
For a 10-second clip of one speaker, the output starts like this:

```
0.487 3.001 asr  The birch canoe slid on the smooth plank.
0.487 3.001 diarization SPEAKER_00
0.487 3.001 language en (98.9%)
0.487 3.001 gender female (99.7%)
0.487 3.001 age 18 - 22 (46.8%)
0.487 3.001 emotion sad (70.6%)
...
0.487 3.001 intensity 0.0873
```

Each row also has `prediction`, the list of all labels with their probabilities. Use `output.model_dump()` to get the results as a dictionary.

Setting `embeddings=True` during audio upload will include speaker and behavioral embeddings in the output (see [documentation](https://behavioralsignals.readme.io/docs/embeddings#/)):

```python
response = client.behavioral.upload_audio(file_path="audio.wav", embeddings=True)
output = client.behavioral.wait_for_result(pid=response.pid, timeout=600)
```

Each HTTP request also has its own time limit: 10 seconds to connect, then up to 60 seconds of waiting for the server (300 seconds for uploads).
You can change these when creating the client, or pass `None` for no limit:

```python
client = Client(YOUR_CID, YOUR_API_KEY, timeout=(10, 120), upload_timeout=(10, 900))
```

These limits apply to single requests. The `timeout` of `wait_for_result` limits the whole wait.
If an upload times out, the server may still have received the file and started a process, so check `list_processes()` (or `list_video_processes()` for videos) before uploading again.

### Behavioral API Streaming Mode

In streaming mode, you can send audio data in real-time to the Behavioral Signals API. The API will return results as they are processed.

```python
from behavioralsignals import Client, StreamingOptions
from behavioralsignals.utils import make_audio_stream

client = Client(YOUR_CID, YOUR_API_KEY)
audio_stream, sample_rate = make_audio_stream("audio.wav", chunk_size=0.25)
options = StreamingOptions(sample_rate=sample_rate, encoding="LINEAR_PCM")

for result in client.behavioral.stream_audio(audio_stream=audio_stream, options=options):
    for item in result.results or []:
        top = item.prediction[0]
        label = item.finalLabel or top.score  # continuous tasks (e.g. intensity) have no label
        if not label:
            continue  # the features row carries embeddings, not a result
        confidence = f" ({float(top.posterior):.1%})" if top.posterior else ""
        print(f"{item.st} {item.et} {item.task} {label}{confidence}")
```

### Deepfakes API Batch Mode

A similar example for the Deepfakes API in batch mode allows you to send audio files for deepfake detection:

```python
from behavioralsignals import Client

client = Client(YOUR_CID, YOUR_API_KEY)

response = client.deepfakes.upload_audio(file_path="audio.wav")
output = client.deepfakes.wait_for_result(pid=response.pid, timeout=600)

for item in output.results or []:
    print(item.st, item.et, item.task, item.finalLabel)
```

Setting `embeddings=True` during audio upload will include speaker and deepfake embeddings in the output (see [documentation](https://behavioralsignals.readme.io/docs/embeddings-1#/)):

```python
response = client.deepfakes.upload_audio(file_path="audio.wav", embeddings=True)
output = client.deepfakes.wait_for_result(pid=response.pid, timeout=600)
```


#### 🔬 Experimental: Deepfake Generator Prediction (Batch Only)

An experimental option is now available that attempts to predict the generator model used to produce a deepfake.
When enabled, the returned results will contain an additional field - only for audios with detected deepfake content - indicating the predicted generator model along with a confidence score.

You can activate this feature by passing `enable_generator_detection=True` during audio upload:

```python
from behavioralsignals import Client

client = Client(YOUR_CID, YOUR_API_KEY)

response = client.deepfakes.upload_audio(file_path="audio.wav", enable_generator_detection=True)
output = client.deepfakes.wait_for_result(pid=response.pid, timeout=600)
```

See more in our [API documentation](https://behavioralsignals.readme.io/docs/generator-detection#/).

#### 🎬 Video Deepfake Detection (Batch Only)

In addition to audio, the Deepfakes API can detect deepfakes in video files. You upload a video the same way you upload audio, and the API analyzes both the audio track and the video frames.

```python
from behavioralsignals import Client

client = Client(YOUR_CID, YOUR_API_KEY)

response = client.deepfakes.upload_video(file_path="video.mp4")
output = client.deepfakes.wait_for_video_result(pid=response.pid, timeout=600)
```

Unlike `wait_for_result`, the video result response returns two separate lists — `audio_results` (deepfake detection on the audio track) and `video_results` (deepfake detection on the video frames):

```python
for item in output.video_results or []:
    print(item.st, item.et, item.task, item.finalLabel)
```

You can also submit a video via an S3 presigned URL with `client.deepfakes.upload_s3_presigned_video_url(url=...)`, and list/inspect video processes with `client.deepfakes.list_video_processes()` and `client.deepfakes.get_video_process(pid=...)`. The `embeddings` and `enable_generator_detection` options are supported and apply to the audio-track results. Video deepfake detection is currently available in batch mode only.

### Deepfakes API Streaming Mode

A similar streaming example for the Deepfakes API allows you to send audio data in real-time for speech deepfake detection:

```python
from behavioralsignals import Client, StreamingOptions
from behavioralsignals.utils import make_audio_stream

client = Client(YOUR_CID, YOUR_API_KEY)
audio_stream, sample_rate = make_audio_stream("audio.wav", chunk_size=0.25)
options = StreamingOptions(sample_rate=sample_rate, encoding="LINEAR_PCM")

for result in client.deepfakes.stream_audio(audio_stream=audio_stream, options=options):
    for item in result.results or []:
        top = item.prediction[0]
        label = item.finalLabel or top.score  # some tasks have no label, only a score
        if not label:
            continue  # the features row carries embeddings, not a result
        confidence = f" ({float(top.posterior):.1%})" if top.posterior else ""
        print(f"{item.st} {item.et} {item.task} {label}{confidence}")
```

## Available Methods

`client.behavioral` and `client.deepfakes` have the same methods for audio. Video methods are only on `client.deepfakes`.

| Method | What it does |
|---|---|
| `upload_audio(file_path, ...)` | Uploads an audio file and returns the process, with its `pid` |
| `upload_s3_presigned_url(url, ...)` | Same as `upload_audio`, for audio at an S3 presigned URL |
| `wait_for_result(pid, timeout=None)` | Waits for a process to finish and returns its results |
| `get_result(pid)` | Returns the results of a finished process |
| `get_process(pid)` | Returns a process and its status |
| `list_processes(page=0, page_size=1000, sort="asc", start_date=None, end_date=None)` | Lists your processes |
| `stream_audio(audio_stream, options)` | Sends audio as a stream and yields results as they arrive |
| `upload_video(file_path, ...)` | Deepfakes only: uploads a video file |
| `upload_s3_presigned_video_url(url, ...)` | Deepfakes only: same as `upload_video`, for a video at an S3 presigned URL |
| `wait_for_video_result(pid, timeout=None)` | Deepfakes only: waits for a video process to finish and returns its results |
| `get_video_result(pid)` | Deepfakes only: returns the results of a finished video process |
| `get_video_process(pid)` | Deepfakes only: returns a video process and its status |
| `list_video_processes(...)` | Deepfakes only: lists your video processes |

## Error Handling

When the API returns an error, the SDK raises `BehavioralSignalsError`. Its `status_code` is the HTTP status code.
`wait_for_result` also raises `TimeoutError` if processing is not done within `timeout` seconds, and `RuntimeError` if the process failed (for example, not enough credits).

```python
from behavioralsignals import BehavioralSignalsError, Client

client = Client(YOUR_CID, YOUR_API_KEY)

try:
    output = client.behavioral.get_result(pid=12345)
except BehavioralSignalsError as error:
    print(error.status_code, error)
```

`BehavioralSignalsError` is a subclass of `Exception`, so code that catches `Exception` keeps working.
Network problems raise the usual `requests` exceptions, such as `requests.ConnectionError`.
