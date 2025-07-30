# Behavioral Signals Python SDK

<p align="center">
  <img src="assets/logo.png" alt="Behavioral Signal Technologies"/>
</p>

<div align="center">



[![Discord](https://badgen.net/discord/members/fxjRrbMH3Q/?color=8978cc&icon=discord)](https://discord.com/invite/fxjRrbMH3Q)
[![Twitter](https://badgen.net/badge/b/behavioralsignals/icon?icon=twitter&label&color=black)](https://x.com/behaviorsignals)
[![readme.io](https://badgen.net/badge/readme.io/Documentation/?color=black)](https://behavioralsignals.readme.io/)
[![PyPI](https://badgen.net/badge/PyPI/behavioralsignals/?color=blue)](https://pypi.org/project/behavioralsignals/)

</div>

Python SDK for the Behavioral Signals API. Behavioral Signals builds AI solutions that understand human behavior through voice and detect deepfake content in audio.
Our API enables developers to integrate behavioral analysis into their applications, both in batch and streaming modes.


## Table of Contents
* [Behavioral Signals Python SDK](#behavioral-signals-python-sdk)
  * [Features](#features)
  * [Requirements](#requirements)
  * [API Key Setup](#api-key-setup)
  * [SDK Installation](#sdk-installation)
  * [SDK Example Usage](#sdk-example-usage)
    * [Behavioral API Batch Mode](#behavioral-api-batch-mode)
    * [Behavioral API Streaming Mode](#behavioral-api-streaming-mode)
    * [Deepfakes API Batch Mode](#deepfakes-api-batch-mode)
    * [Deepfakes API Streaming Mode](#deepfakes-api-streaming-mode)

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
You can also find more detailed examples for both [batch](examples/batch/README.md) and [streaming](examples/streaming/README.md) in the `examples/` directory.

### Behavioral API Batch Mode

In batch mode, you can send audio files to the Behavioral Signals API for analysis. The API will return a unique process ID (PID) that you can use to retrieve the results later.

```python
from behavioralsignals import Client

client = Client(YOUR_CID, YOUR_API_KEY)

response = client.behavioral.upload_audio(file_path="audio.wav")
output = client.behavioral.get_result(pid=response.pid)
```

### Behavioral API Streaming Mode

In streaming mode, you can send audio data in real-time to the Behavioral Signals API. The API will return results as they are processed.

```python
from behavioralsignals import Client, StreamingOptions
from behavioralsignals.utils import make_audio_stream

client = Client(YOUR_CID, YOUR_API_KEY)
audio_stream, sample_rate = make_audio_stream("audio.wav", chunk_size=250)
options = StreamingOptions(sample_rate=sample_rate, encoding="LINEAR_PCM")

for result in client.behavioral.stream_audio(audio_stream=audio_stream, options=options):
    print(result)
```

### Deepfakes API Batch Mode

A similar example for the Deepfakes API in batch mode allows you to send audio files for deepfake detection:

```python
from behavioralsignals import Client

client = Client(YOUR_CID, YOUR_API_KEY)

response = client.deepfakes.upload_audio(file_path="audio.wav")
output = client.deepfakes.get_result(pid=response.pid)
```

### Deepfakes API Streaming Mode

A similar streaming example for the Deepfakes API allows you to send audio data in real-time for speech deepfake detection:

```python
from behavioralsignals import Client, StreamingOptions
from behavioralsignals.utils import make_audio_stream

client = Client(YOUR_CID, YOUR_API_KEY)
audio_stream, sample_rate = make_audio_stream("audio.wav", chunk_size=250)
options = StreamingOptions(sample_rate=sample_rate, encoding="LINEAR_PCM")

for result in client.deepfakes.stream_audio(audio_stream=audio_stream, options=options):
    print(result)
```