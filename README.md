# Behavioral Signals Python SDK

<p align="center">
  <img src="assets/logo.png" alt="Behavioral Signal Technologies"/>
</p>

<div align="center">

[![Discord](https://badgen.net/discord/members/sSJ88FZG/?color=8978cc&icon=discord)](https://discord.gg/sSJ88FZG)
[![Twitter](https://badgen.net/badge/b/behavioralsignals/icon?icon=twitter&label&color=8978cc)](https://x.com/behaviorsignals)
[![readme.io](https://badgen.net/badge/readme.io/Documentation/?color=8978cc)](https://behavioralsignals.readme.io/)

</div>

Python SDK for the Behavioral Signals REST and Streaming APIs. Behavioral Signals builds AI solutions that understand human behavior through voice and detect deepfake content in audio.
Our API enables developers to integrate behavioral analysis into their applications, both in real-time and offline modes.

## Install

```bash
pip install behavioralsignals
```

## Usage

First, create an account and obtain your API key from the [Behavioral Signals portal](https://portal.behavioralsignals.com/).
After obtaining your API key, you can use the SDK to interact with the Behavioral Signals APIs.
Below, we provide examples for both batch and streaming modes. You can also find more detailed examples for both cases in the `examples/` directory.

## Batch Mode

In batch mode, you can send audio files to the Behavioral Signals API for analysis. The API will return a unique process ID (PID) that you can use to retrieve the results later.

```python
from behavioralsignals import Client

client = Client(YOUR_USER_ID, YOUR_API_KEY)

response = client.send_audio(file="audio.wav")
output = client.get_result(pid=response["pid"])
```

See more examples [here](examples/batch/README.md).


## Streaming Mode

In streaming mode, you can send audio data in real-time to the Behavioral Signals API. The API will return results as they are processed.

```python
from behavioralsignals import Client
from behavioralsignals.utils import create_audio_stream

client = Client(YOUR_USER_ID, YOUR_API_KEY)
audio_stream = create_audio_stream("audio.wav", sample_rate=16000, chunk_size=250)
streaming_options = {"sample_rate": 16000}

for result in client.send_audio_stream(audio_stream=audio_stream, streaming_options=streaming_options):
     print(result)
```

See more examples [here](examples/streaming/README.md).