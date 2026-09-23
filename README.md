# Behavioral Signals API Python SDK

<p align="center">
  <img src="https://raw.githubusercontent.com/BehavioralSignalTechnologies/behavioralsignals-python/main/assets/logo.png" alt="Behavioral Signal Technologies"/>
</p>

<div align="center">

[![Discord](https://badgen.net/discord/members/fxjRrbMH3Q/?color=8978cc&icon=discord)](https://discord.com/invite/fxjRrbMH3Q)
[![Twitter](https://badgen.net/badge/b/behavioralsignals/icon?icon=twitter&label&color=black)](https://x.com/behaviorsignals)
[![readme.io](https://badgen.net/badge/readme.io/Documentation/?color=black)](https://behavioralsignals.readme.io/)
[![CI](https://github.com/BehavioralSignalTechnologies/behavioralsignals-python/actions/workflows/ci.yml/badge.svg)](https://github.com/BehavioralSignalTechnologies/behavioralsignals-python/actions/workflows/ci.yml)
[![Coverage](https://raw.githubusercontent.com/BehavioralSignalTechnologies/behavioralsignals-python/python-coverage-comment-action-data/badge.svg)](https://github.com/BehavioralSignalTechnologies/behavioralsignals-python/tree/python-coverage-comment-action-data)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![PyPI](https://badgen.net/pypi/v/behavioralsignals)](https://pypi.org/project/behavioralsignals/)
[![Status](https://img.shields.io/pypi/status/behavioralsignals)](https://pypi.org/project/behavioralsignals/)
[![Downloads](https://badgen.net/pypi/dm/behavioralsignals)](https://pypistats.org/packages/behavioralsignals)
[![Python](https://badgen.net/pypi/python/behavioralsignals)](https://pypi.org/project/behavioralsignals/)
[![License](https://badgen.net/badge/license/Apache-2.0/blue)](https://github.com/BehavioralSignalTechnologies/behavioralsignals-python/blob/main/LICENSE)
[![Contributor Covenant](https://badgen.net/badge/Contributor%20Covenant/2.1/4baaaa)](https://github.com/BehavioralSignalTechnologies/behavioralsignals-python/blob/main/CODE_OF_CONDUCT.md)

</div>

Official Python SDK for the [Behavioral Signals API](https://behavioralsignals.readme.io/).

Analyze human behavior and detect deepfake speech using batch and real-time audio APIs. Experimental video deepfake detection is also available in batch mode.

[Python SDK Documentation](https://behavioralsignals.readme.io/docs/behavioral-signals-python-sdk) ·
[Examples](examples/) ·
[PyPI](https://pypi.org/project/behavioralsignals/) ·
[Contributing](CONTRIBUTING.md)

## Quickstart

### Install

```bash
pip install behavioralsignals
```

Requires Python 3.10 or later.

### Configure credentials

Create an account and API key in the [Behavioral Signals portal](https://portal.behavioralsignals.com/).

Set your client ID (CID) and API key as environment variables:

```bash
export BEHAVIORALSIGNALS_CID="your_cid"
export BEHAVIORALSIGNALS_API_KEY="your_api_key"
```

The SDK will pick them up automatically:

```python
from behavioralsignals import Client

client = Client()
```

You can also pass the credentials directly:

```python
client = Client("your_cid", "your_api_key")
```

### Analyze audio

```python
from behavioralsignals import Client

client = Client()

process = client.behavioral.upload_audio(file_path="audio.wav")
result = client.behavioral.wait_for_result(
    pid=process.pid,
    timeout=600,
)

print(result.model_dump())
```

`upload_audio()` returns a process with a unique process ID (`pid`). `wait_for_result()` polls until processing completes and returns the analysis result.

## Features

- **Behavioral Analysis** — analyze human behavior from speech in batch and real-time streaming modes
- **Deepfake Detection** — detect synthetic or manipulated speech in batch and real-time streaming modes
- **Video Deepfake Detection (Experimental, Batch Only)** — analyze both the video frames and audio track of supported video files
- **Core Speech Attributes (Batch Only)** — automatic speech recognition (ASR), speaker diarization, and language identification
- **Embeddings** — retrieve speaker and behavioral embeddings from the Behavioral API, or speaker and deepfake embeddings from the Deepfakes API
- **S3 Input** — submit audio and video using S3 presigned URLs
- **MCP Server** — use Behavioral Signals from MCP-compatible AI assistants

## Streaming

Both the Behavioral and Deepfakes APIs support real-time **audio** streaming over gRPC.

To stream an audio file:

```python
from behavioralsignals import Client, StreamingOptions
from behavioralsignals.utils import make_audio_stream

client = Client()

audio_stream, sample_rate = make_audio_stream(
    "audio.wav",
    chunk_size=0.25,
)

options = StreamingOptions(
    sample_rate=sample_rate,
    encoding="LINEAR_PCM",
)

for result in client.behavioral.stream_audio(
    audio_stream=audio_stream,
    options=options,
):
    print(result)
```

`chunk_size` is specified in **seconds**, so `0.25` corresponds to 250 ms.

`stream_audio()` can also accept your own `Iterator[bytes]`, for example from a microphone or live call.

For real-time deepfake detection, use the same interface:

```python
for result in client.deepfakes.stream_audio(
    audio_stream=audio_stream,
    options=options,
):
    print(result)
```

See the [streaming examples](examples/streaming/) and [streaming documentation](https://behavioralsignals.readme.io/docs/streaming-using-python-sdk) for more.

## Deepfake Detection

### Audio

Batch deepfake detection follows the same workflow as Behavioral Analysis:

```python
from behavioralsignals import Client

client = Client()

process = client.deepfakes.upload_audio(file_path="audio.wav")
result = client.deepfakes.wait_for_result(
    pid=process.pid,
    timeout=600,
)

print(result.model_dump())
```

To include speaker and deepfake embeddings:

```python
process = client.deepfakes.upload_audio(
    file_path="audio.wav",
    embeddings=True,
)
```

### Experimental Generator Detection

Generator detection is an experimental batch feature that attempts to identify the model used to generate deepfake audio.

```python
process = client.deepfakes.upload_audio(
    file_path="audio.wav",
    enable_generator_detection=True,
)
```

See the [generator detection documentation](https://behavioralsignals.readme.io/docs/generator-detection) for details and supported generators.

### Experimental Video Deepfake Detection

Video deepfake detection is available in **batch mode only** and is currently experimental.

```python
process = client.deepfakes.upload_video(file_path="video.mp4")
result = client.deepfakes.wait_for_video_result(
    pid=process.pid,
    timeout=600,
)
```

Unlike an audio result, a video result contains two separate lists:

- `audio_results` — deepfake detection results for the video's audio track
- `video_results` — deepfake detection results for the video frames

For example:

```python
for item in result.video_results or []:
    print(item)
```

You can also submit a video using an S3 presigned URL with `upload_s3_presigned_video_url()` and inspect video processes using `list_video_processes()` and `get_video_process()`.

See the [video deepfake documentation](https://behavioralsignals.readme.io/docs/submit-a-file-for-processing) for supported formats, limits, and the current experimental status.

## Available Methods

`client.behavioral` and `client.deepfakes` expose the same methods for audio. Video methods are available only on `client.deepfakes`.

| Method | What it does |
|---|---|
| `upload_audio(file_path, ...)` | Uploads an audio file and returns the process, including its `pid` |
| `upload_s3_presigned_url(url, ...)` | Submits audio using an S3 presigned URL |
| `wait_for_result(pid, timeout=None)` | Waits for a process to finish and returns its results |
| `get_result(pid)` | Returns the results of a finished process |
| `get_process(pid)` | Returns a process and its current status |
| `list_processes(...)` | Lists audio processes |
| `stream_audio(audio_stream, options)` | Streams audio and yields results as they arrive |
| `upload_video(file_path, ...)` | Deepfakes only: uploads a video file |
| `upload_s3_presigned_video_url(url, ...)` | Deepfakes only: submits video using an S3 presigned URL |
| `wait_for_video_result(pid, timeout=None)` | Deepfakes only: waits for a video process to finish and returns its results |
| `get_video_result(pid)` | Deepfakes only: returns the results of a finished video process |
| `get_video_process(pid)` | Deepfakes only: returns a video process and its status |
| `list_video_processes(...)` | Deepfakes only: lists video processes |

For detailed parameters and result schemas, see the [full API documentation](https://behavioralsignals.readme.io/).

## Timeouts and Error Handling

### Batch API

Batch HTTP API errors raise `BehavioralSignalsError`. Its `status_code` contains the HTTP status code.

```python
from behavioralsignals import BehavioralSignalsError, Client

client = Client()

try:
    result = client.behavioral.get_result(pid=12345)
except BehavioralSignalsError as error:
    print(error.status_code, error)
```

`wait_for_result()` and `wait_for_video_result()` also raise:

- `TimeoutError` if processing has not finished within the supplied `timeout`
- `RuntimeError` if the process finishes unsuccessfully, for example because of insufficient credits

Network problems raise the usual `requests` exceptions, such as `requests.ConnectionError`.

Each HTTP request also has its own timeout. By default, the SDK allows 10 seconds to connect and up to 60 seconds waiting for the server, or 300 seconds for uploads.

You can customize these limits when creating the client:

```python
client = Client(
    timeout=(10, 120),
    upload_timeout=(10, 900),
)
```

These request timeouts are separate from the overall `timeout` passed to `wait_for_result()`.

> If an upload request times out, the server may still have received the file and started processing it. Check `list_processes()` — or `list_video_processes()` for videos — before uploading the same file again.

### Streaming API

Streaming uses gRPC rather than the batch HTTP API. Streaming failures can therefore raise `grpc.RpcError` instead of `BehavioralSignalsError`.

```python
import grpc

try:
    for result in client.behavioral.stream_audio(
        audio_stream=audio_stream,
        options=options,
    ):
        print(result)
except grpc.RpcError as error:
    print(error.code(), error.details())
```

## Use with AI Assistants (MCP)

The SDK includes an [MCP](https://modelcontextprotocol.io/) server (available since version 0.7.0), so AI assistants such as Claude Code, Codex, Claude Desktop, and Cursor can analyze audio and video files for you.

The setups below start the server with `uvx`, so install [uv](https://docs.astral.sh/uv/) first.

The server reads credentials from `BEHAVIORALSIGNALS_CID` and `BEHAVIORALSIGNALS_API_KEY`. Your assistant starts the server, so provide them in the assistant's MCP configuration as shown below.

### Claude Code

With the two variables set in your shell, run:

```bash
claude mcp add --env BEHAVIORALSIGNALS_CID="$BEHAVIORALSIGNALS_CID" \
  --env BEHAVIORALSIGNALS_API_KEY="$BEHAVIORALSIGNALS_API_KEY" --transport stdio \
  behavioralsignals -- uvx --python ">=3.10" --from "behavioralsignals[mcp]" behavioralsignals-mcp
```

This adds the server to the current project only. Your key stays out of your shell history and out of the repository.

### Codex

With the two variables set in your shell, run:

```bash
codex mcp add behavioralsignals --env BEHAVIORALSIGNALS_CID="$BEHAVIORALSIGNALS_CID" \
  --env BEHAVIORALSIGNALS_API_KEY="$BEHAVIORALSIGNALS_API_KEY" \
  -- uvx --python ">=3.10" --from "behavioralsignals[mcp]" behavioralsignals-mcp
```

This adds the server for all your projects in `~/.codex/config.toml`.

### Claude Desktop and Cursor

Add this to `claude_desktop_config.json` (Claude Desktop: **Settings > Developer > Edit Config**) or `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "behavioralsignals": {
      "command": "uvx",
      "args": [
        "--python",
        ">=3.10",
        "--from",
        "behavioralsignals[mcp]",
        "behavioralsignals-mcp"
      ],
      "env": {
        "BEHAVIORALSIGNALS_CID": "your_cid",
        "BEHAVIORALSIGNALS_API_KEY": "your_api_key"
      }
    }
  }
}
```

If the app cannot find `uvx`, use its full path (`which uvx`).

### MCP Tools

The server exposes four tools:

| Tool | What it does |
|---|---|
| `analyze_behavior` | Uploads an audio file or S3 presigned URL for behavioral analysis and returns the results |
| `detect_deepfake` | Uploads an audio or video file, or an S3 presigned URL, for deepfake detection and returns the results |
| `get_result` | Returns the results of a process, in pages, optionally filtered to specific tasks |
| `list_processes` | Lists processes, newest first, including the failure reason when available |

Notes:

- Each upload uses API credits, and files named in MCP tool calls are sent to the Behavioral Signals API.
- Upload tools wait up to `wait_seconds` (45 seconds by default, 50 seconds at most). If processing takes longer, they return the process ID so the assistant can check it later with `get_result`.
- Do not commit configuration files containing your API key.

### Running the MCP Server Manually

With `uv` installed, run the server without installing the package:

```bash
uvx --python ">=3.10" --from "behavioralsignals[mcp]" behavioralsignals-mcp
```

Or install the MCP extra with pip:

```bash
pip install "behavioralsignals[mcp]"
behavioralsignals-mcp
```

## Requirements

- Python 3.10+
- A Behavioral Signals account and API key

`ffmpeg` is needed by `make_audio_stream()` for formats other than WAV, such as mp3.

## Documentation and Examples

- [Python SDK Documentation](https://behavioralsignals.readme.io/docs/behavioral-signals-python-sdk)
- [Full API Documentation](https://behavioralsignals.readme.io/)
- [Streaming with the Python SDK](https://behavioralsignals.readme.io/docs/streaming-using-python-sdk)
- [Video Deepfake Detection](https://behavioralsignals.readme.io/docs/submit-a-file-for-processing)
- [Batch Examples](examples/batch/)
- [Streaming Examples](examples/streaming/)
- [AI-friendly Documentation (`llms.txt`)](https://behavioralsignals.readme.io/llms.txt)

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, formatting, and pull request guidelines.

Please report security issues according to [SECURITY.md](SECURITY.md).

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).
