"""Output helpers and the stable exit-code contract shared by all hbot commands."""
import json
from enum import IntEnum
from typing import Any

import typer


class ExitCode(IntEnum):
    """Stable exit codes so an agentic harness can branch on outcomes."""
    SUCCESS = 0
    ERROR = 1            # generic failure
    NOT_FOUND = 2        # instance does not exist
    NOT_RUNNING = 3      # instance exists but its process is not alive
    CONFIG_ERROR = 4     # missing/invalid config or password
    TIMEOUT = 5          # operation did not complete in time


def print_json(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, default=str, sort_keys=False))


def fail(message: str, code: ExitCode, *, json_output: bool) -> "typer.Exit":
    """Emit an error in the requested format and raise to exit with ``code``."""
    if json_output:
        print_json({"ok": False, "error": message, "code": int(code)})
    else:
        typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(int(code))
