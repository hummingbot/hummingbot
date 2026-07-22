"""Output helpers + the stable exit-code contract shared by all hbot commands.

hbot emits a token-economic **Markdown** format by default — tables for lists of records, key-value
for single records — that serves both humans and agents. The run/observe commands (start, stop,
status, logs, config, balance, deploy) also take ``--json`` for a machine-readable object with raw
values. Either way, the machine contract for outcomes is the stable **exit code** (branch on it).
"""
import json
import textwrap
from enum import IntEnum
from typing import Any, Dict, List, Optional, Sequence

import typer
from typer.core import TyperGroup


class SortedCommandsGroup(TyperGroup):
    """A Typer group that lists its sub-commands alphabetically in --help instead of registration
    order. Pass as ``cls=`` to every ``typer.Typer(...)`` so all menus read alphabetically."""

    def list_commands(self, ctx: "typer.Context") -> List[str]:
        return sorted(super().list_commands(ctx))


class ExitCode(IntEnum):
    """Stable exit codes so an agentic harness can branch on outcomes."""
    SUCCESS = 0
    ERROR = 1            # generic failure
    NOT_FOUND = 2        # instance does not exist
    NOT_RUNNING = 3      # instance exists but its process is not alive
    CONFIG_ERROR = 4     # missing/invalid config or password
    TIMEOUT = 5          # operation did not complete in time


def cell(v: Any) -> str:
    """Format one value for a Markdown cell/line: compact, single-line, pipe-escaped."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v).replace("|", "\\|").replace("\n", " ")


def _wrap_cell(value: str, width: Optional[int]) -> List[str]:
    """Split one formatted cell value into lines no wider than ``width`` (one line if it fits)."""
    if width is None or len(value) <= width:
        return [value]
    return textwrap.wrap(value, width=width, break_long_words=True, break_on_hyphens=False) or [""]


def render_table(rows: Sequence[dict], columns: Optional[List[str]] = None,
                 title: Optional[str] = None,
                 max_widths: Optional[Dict[str, int]] = None) -> str:
    """Render a list of records as an aligned Markdown table (token-economic format for tabular
    output).

    ``max_widths`` bounds named columns (e.g. ``{"value": 120}``): a cell wider than its bound
    wraps onto continuation lines whose sibling cells stay blank, so one large structured value
    can't stretch its whole row into an unreadable line.

    The last column is not padded (a ragged right edge): the trailing padding would buy nothing
    for readability but costs ~10% more tokens on table-heavy commands.
    """
    head = f"## {title}\n\n" if title else ""
    rows = list(rows)
    if not rows:
        return head + "_(none)_"
    cols = columns or list(rows[0].keys())
    limits = max_widths or {}
    wrapped = [[_wrap_cell(cell(r.get(c)), limits.get(c)) for c in cols] for r in rows]
    widths = [max(len(c), *(len(seg) for row in wrapped for seg in row[i]))
              for i, c in enumerate(cols)]

    def line(values: List[str]) -> str:
        cells = [v.ljust(w) for v, w in zip(values, widths)]
        cells[-1] = values[-1]
        return "| " + " | ".join(cells) + " |"

    lines = [line(cols), "| " + " | ".join("-" * w for w in widths) + " |"]
    for row in wrapped:
        for i in range(max(len(segs) for segs in row)):
            lines.append(line([segs[i] if i < len(segs) else "" for segs in row]))
    return head + "\n".join(lines)


def render_kv(record: dict, title: Optional[str] = None) -> str:
    """Render a single record as a Markdown key-value block."""
    head = f"## {title}\n\n" if title else ""
    if not record:
        return head + "_(empty)_"
    return head + "\n".join(f"- {k}: {cell(v)}" for k, v in record.items())


def echo(text: str) -> None:
    typer.echo(text)


def emit(payload: Any, markdown: str, as_json: bool) -> None:
    """Print ``markdown`` (the default surface) or ``payload`` as JSON when ``--json`` was passed.

    ``payload`` carries the raw values (numbers stay numbers; Decimals and other non-JSON types
    serialize via ``str``) so agents don't re-parse the human rendering.
    """
    typer.echo(json.dumps(payload, indent=2, default=str) if as_json else markdown)


def json_option() -> Any:
    """The shared ``--json`` flag declaration, so every command words it identically."""
    return typer.Option(False, "--json", help="Emit machine-readable JSON instead of Markdown.")


def fail(message: str, code: ExitCode) -> "typer.Exit":
    """Print an error to stderr and exit with the stable ``code`` (the agent branches on the code)."""
    typer.echo(f"Error: {message} (code {int(code)})", err=True)
    raise typer.Exit(int(code))
