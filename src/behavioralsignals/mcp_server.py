"""MCP server that lets AI assistants run Behavioral Signals analyses.

Run it with `behavioralsignals-mcp` after `pip install "behavioralsignals[mcp]"`. It talks MCP
over stdio, so it must never print to stdout.
"""

import json
from typing import Literal, Annotated
from contextlib import contextmanager

from pydantic import Field


try:
    from mcp.types import ToolAnnotations
    from mcp.server import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError as error:
    raise ImportError(
        "The MCP server needs the mcp package; install it with: "
        "pip install 'behavioralsignals[mcp]'"
    ) from error

from .base import BehavioralSignalsError
from .models import ResultItem
from .deepfakes import Deepfakes
from .behavioral import Behavioral


Analysis = Literal["behavioral", "deepfake_audio", "deepfake_video"]
WaitSeconds = Annotated[float, Field(ge=0)]

DEFAULT_WAIT = 45
DEFAULT_LIMIT = 300
RESULT_COLUMNS = ["start", "end", "task", "label", "confidence"]
READ_ONLY = ToolAnnotations(read_only_hint=True)

server = MCPServer(
    "Behavioral Signals",
    instructions=(
        "Analyze speech for emotion and behavior, and detect audio or video deepfakes. "
        "Upload tools wait up to wait_seconds, then return the results or a pid. "
        "Call get_result with that pid for a job that is still processing, for more rows, "
        "or to filter tasks. Each upload uses credits."
    ),
)


@server.tool(annotations=READ_ONLY, structured_output=False)
def get_result(
    pid: int,
    analysis: Analysis,
    tasks: list[str] | None = None,
    offset: Annotated[int, Field(ge=0)] = 0,
    limit: Annotated[int, Field(ge=1, le=1000)] = DEFAULT_LIMIT,
    wait_seconds: WaitSeconds = DEFAULT_WAIT,
) -> str:
    """Returns the results of a job, waiting up to wait_seconds if it is still processing.

    `analysis` is the kind of job: "behavioral" (analyze_behavior), "deepfake_audio" or
    "deepfake_video" (detect_deepfake). Results come as tab-separated rows, `limit` rows from
    `offset`. `tasks` keeps only those tasks, e.g. ["emotion"]; the header lists the task names.
    """
    with _tool_errors(), _api(analysis) as api:
        return _result_text(api, analysis, pid, wait_seconds, tasks, offset, limit)


def main():
    """Runs the MCP server over stdio."""
    server.run()


def _api(analysis: str) -> Behavioral | Deepfakes:
    """Returns a new API client; the credentials come from the environment."""
    return Behavioral() if analysis == "behavioral" else Deepfakes()


@contextmanager
def _tool_errors():
    """Turns expected errors into ToolError, the only kind whose message reaches the model."""
    try:
        yield
    except (ValueError, OSError, RuntimeError, BehavioralSignalsError) as error:
        raise ToolError(str(error)) from error


def _result_text(
    api: Behavioral | Deepfakes,
    analysis: str,
    pid: int,
    wait_seconds: float,
    tasks: list[str] | None,
    offset: int,
    limit: int,
) -> str:
    """Waits up to wait_seconds for the result and formats one page of it."""
    wait = api.wait_for_video_result if analysis == "deepfake_video" else api.wait_for_result
    try:
        result = wait(pid=pid, timeout=wait_seconds)
    except TimeoutError:
        retry = _call("get_result", pid=pid, analysis=analysis)
        return f"pid {pid} is still processing. Call {retry} to wait again."
    return _format_result(pid, analysis, _result_rows(result, analysis), tasks, offset, limit)


def _result_rows(result, analysis: str) -> list[list[str]]:
    """Returns the rows that have a label; video rows start with their track."""
    if analysis != "deepfake_video":
        return _labelled_rows(result.results)
    audio = [["audio", *row] for row in _labelled_rows(result.audio_results)]
    video = [["video", *row] for row in _labelled_rows(result.video_results)]
    return audio + video


def _labelled_rows(items: list[ResultItem] | None) -> list[list[str]]:
    rows = (_result_row(item) for item in items or [])
    return [row for row in rows if row]


def _result_row(item: ResultItem) -> list[str] | None:
    """Returns the item as a row, or None if it has no label (e.g. the features row)."""
    top = item.prediction[0] if item.prediction else None
    label = item.finalLabel or (top.score if top else None)
    if not label:
        return None
    confidence = top.posterior if top else None
    return [_cell(value) for value in (item.startTime, item.endTime, item.task, label, confidence)]


def _format_result(
    pid: int,
    analysis: str,
    rows: list[list[str]],
    tasks: list[str] | None,
    offset: int,
    limit: int,
) -> str:
    """Formats the rows of the tasks, `limit` rows from `offset`, as a tab-separated table."""
    columns = (["track"] if analysis == "deepfake_video" else []) + RESULT_COLUMNS
    task_index = columns.index("task")
    task_names = ", ".join(sorted({row[task_index] for row in rows}))
    if tasks:
        rows = [row for row in rows if row[task_index] in tasks]
    total = len(rows)
    if total == 0:
        hint = f" Tasks: {task_names}" if tasks and task_names else ""
        return f"pid {pid} completed. No result rows.{hint}"
    if offset >= total:
        return f"pid {pid} completed. No rows at offset {offset}; there are {total} rows."
    page = rows[offset : offset + limit]
    end = offset + len(page)
    lines = [
        f"pid {pid} completed. Rows {offset + 1}-{end} of {total}. Tasks: {task_names}",
        _tsv(columns),
        *(_tsv(row) for row in page),
    ]
    if end < total:
        more = _call("get_result", pid=pid, analysis=analysis, tasks=tasks, offset=end)
        lines.append(f"More rows: {more}")
    return "\n".join(lines)


def _call(tool: str, **args) -> str:
    """Formats a tool call for a hint, leaving out args that are None."""
    shown = ", ".join(
        f"{name}={json.dumps(value)}" for name, value in args.items() if value is not None
    )
    return f"{tool}({shown})"


def _tsv(cells: list[str]) -> str:
    return "\t".join(cells)


def _cell(value) -> str:
    """Formats a table cell: None is empty, and tabs and newlines become spaces."""
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\n", " ")
