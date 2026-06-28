"""``hbot logs`` — tail a bot's log file."""
import json
import time
from pathlib import Path
from typing import Optional

import typer

from hummingbot.cli.instances import Instance, tail_lines
from hummingbot.cli.output import ExitCode, fail


def _resolve_log_file(instance: Instance) -> Optional[Path]:
    if instance.structured_log_file.exists():
        return instance.structured_log_file
    if instance.log_file.exists():
        return instance.log_file
    return None


def logs(
    name: str = typer.Argument(..., help="Instance id."),
    lines: int = typer.Option(200, "--lines", "-n", help="Number of trailing lines to show."),
    follow: bool = typer.Option(False, "--follow", "-f", help="Stream new lines until interrupted (Ctrl-C)."),
    json_output: bool = typer.Option(
        False, "--json", help="JSON: a {lines:[...]} object for a snapshot, or NDJSON (one record/line) with -f."),
) -> None:
    """Print the tail of the bot's log; ``-f`` streams new lines as they are written.

    Note for agents: ``-f`` runs until interrupted — bound it (e.g. a timeout) rather than awaiting forever.
    """
    instance = Instance(name)
    if not instance.exists():
        fail(f"instance '{name}' not found", ExitCode.NOT_FOUND, json_output=json_output)

    log_file = _resolve_log_file(instance)
    if log_file is None:
        fail(f"no log file for '{name}' yet", ExitCode.ERROR, json_output=json_output)

    tail = tail_lines(log_file, lines)

    # Snapshot (no --follow): emit one JSON object (parseable in a single read), or plain text.
    if not follow:
        if json_output:
            typer.echo(json.dumps({"ok": True, "name": name, "source": str(log_file), "lines": tail}, default=str))
        else:
            for line in tail:
                typer.echo(line)
        return

    # Follow: stream. JSON mode emits NDJSON (one compact record per line) so it stays parseable.
    def emit(line: str) -> None:
        line = line.rstrip("\n")
        typer.echo(json.dumps({"name": name, "line": line}) if json_output else line)

    for line in tail:
        emit(line)
    with open(log_file, "r", errors="replace") as f:
        f.seek(0, 2)  # end of file
        try:
            while True:
                line = f.readline()
                if line:
                    emit(line)
                else:
                    time.sleep(0.5)
        except KeyboardInterrupt:
            return
