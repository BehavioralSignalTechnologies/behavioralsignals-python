# AGENTS.md

Python SDK for the [Behavioral Signals API](https://behavioralsignals.readme.io/): voice behavior
analysis and audio/video deepfake detection, plus an optional MCP server. Setup, code style and
pull request steps are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Map

- `src/behavioralsignals/client.py`: `Client`, which holds the `behavioral` and `deepfakes` clients.
- `src/behavioralsignals/behavioral.py`, `deepfakes.py`: the two APIs. `base.py`: HTTP requests,
  errors, the wait loop behind `wait_for_result`, and the gRPC channel.
- `src/behavioralsignals/models.py`: pydantic models of requests and responses.
  `configuration.py`: API URLs and timeouts.
- `src/behavioralsignals/mcp_server.py`: the MCP server (`behavioralsignals-mcp`).
- `src/behavioralsignals/generated/`: gRPC code generated from `protos/api.proto`.
- `examples/`: batch and streaming scripts. `tests/`: pytest tests.

## Commands

```bash
uv pip install -e ".[dev]"  # in a venv, see CONTRIBUTING.md
pytest
ruff check
ruff format
```

CI runs `ruff check`, `ruff format --check` and `pytest` on Python 3.10 to 3.13.

## Rules

- Support Python 3.10: no newer syntax or modules.
- `Behavioral` and `Deepfakes` repeat the audio methods; change both.
- Don't edit `generated/` by hand; regenerate it (see CONTRIBUTING.md).
- Tests never call the API and need no credentials. Fake HTTP as `tests/test_client.py` does.
- `mcp` is an optional extra: never import `mcp_server` from `__init__.py`.
- `mcp_server.py` must never print to stdout; stdout carries the MCP protocol.
- When a public method changes, update the README method table, `examples/`, and the MCP tools
  and README MCP section if they use it.
- Never commit credentials.
