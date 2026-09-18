# Contributing

Thanks for helping improve the Behavioral Signals API Python SDK. By taking part, you agree to
follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Report a bug or ask for a feature

Open an [issue](https://github.com/BehavioralSignalTechnologies/behavioralsignals-python/issues/new/choose).
Never paste your API key or CID in an issue.

To report a security problem, follow [SECURITY.md](SECURITY.md) instead.

## Set up

You need Python 3.10+, [ffmpeg](https://ffmpeg.org/) and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/BehavioralSignalTechnologies/behavioralsignals-python.git
cd behavioralsignals-python
uv venv -p python3.10 venv
source venv/bin/activate
uv pip install -e ".[dev]"
```

To call the API, get a CID and API key from the
[Behavioral Signals portal](https://portal.behavioralsignals.com/). The [examples](examples/) read
them from the `BEHAVIORALSIGNALS_CID` and `BEHAVIORALSIGNALS_API_KEY` environment variables.

## Code style

We use [ruff](https://docs.astral.sh/ruff/) with the settings in `ruff.toml` (line length 100).
The dev install above includes the ruff version we use. Before you open a pull request, run:

```bash
ruff check
ruff format
```

## Regenerate the gRPC code

You only need this if you change `protos/api.proto`. Use grpcio-tools 1.73.1, which matches the
`grpcio` minimum in `pyproject.toml`. The generated code does not run on a grpcio older than the
grpcio-tools that generated it, so if you use a newer grpcio-tools, raise that minimum to match.

```bash
uv pip install grpcio-tools==1.73.1
python -m grpc_tools.protoc -I protos \
  --python_out=src/behavioralsignals/generated \
  --pyi_out=src/behavioralsignals/generated \
  --grpc_python_out=src/behavioralsignals/generated \
  protos/api.proto
```

Then, in `src/behavioralsignals/generated/api_pb2_grpc.py`, change `import api_pb2 as api__pb2` to
`from . import api_pb2 as api__pb2`.

## Pull requests

1. Create a branch from `main`.
2. Keep each pull request to one change.
3. If you change how the SDK is used, update `README.md` and `examples/`.
4. If the change needs a new release, bump `version` in `pyproject.toml`.
5. Open the pull request and fill in the template.
