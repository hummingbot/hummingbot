"""Output helpers + the stable exit-code contract shared by all hbot commands.

hbot emits a single, token-economic **Markdown** format — tables for lists of records, key-value for
single records — that serves both humans and agents (no ``--json`` flag). The machine contract for an
agent is the stable **exit code** (branch on it); the Markdown body carries the values.
"""
from enum import IntEnum
from typing import Any, List, Optional, Sequence

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


def render_table(rows: Sequence[dict], columns: Optional[List[str]] = None,
                 title: Optional[str] = None) -> str:
    """Render a list of records as a Markdown table (token-economic format for tabular output)."""
    head = f"## {title}\n\n" if title else ""
    rows = list(rows)
    if not rows:
        return head + "_(none)_"
    cols = columns or list(rows[0].keys())
    lines = ["| " + " | ".join(cols) + " |",
             "| " + " | ".join("---" for _ in cols) + " |"]
    lines += ["| " + " | ".join(cell(r.get(c)) for c in cols) + " |" for r in rows]
    return head + "\n".join(lines)


def render_kv(record: dict, title: Optional[str] = None) -> str:
    """Render a single record as a Markdown key-value block."""
    head = f"## {title}\n\n" if title else ""
    if not record:
        return head + "_(empty)_"
    return head + "\n".join(f"- {k}: {cell(v)}" for k, v in record.items())


def echo(text: str) -> None:
    typer.echo(text)


def fail(message: str, code: ExitCode) -> "typer.Exit":
    """Print an error to stderr and exit with the stable ``code`` (the agent branches on the code)."""
    typer.echo(f"Error: {message} (code {int(code)})", err=True)
    raise typer.Exit(int(code))
