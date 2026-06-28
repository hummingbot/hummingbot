"""``hbot logs`` — tail a bot's log file."""
import time
from pathlib import Path
from typing import Optional

import typer

from hummingbot import prefix_path
from hummingbot.cli.instances import Instance
from hummingbot.cli.output import ExitCode, fail, print_json


def _structured_log_path(name: str) -> Path:
    # Matches conf/hummingbot_logs.yml: $PROJECT_DIR/logs/logs_$STRATEGY_FILE_PATH.log
    return Path(prefix_path()) / "logs" / f"logs_{name}.log"


def _resolve_log_file(instance: Instance) -> Optional[Path]:
    structured = _structured_log_path(instance.name)
    if structured.exists():
        return structured
    if instance.log_file.exists():
        return instance.log_file
    return None


def logs(
    name: str = typer.Argument(..., help="Instance id."),
    lines: int = typer.Option(200, "--lines", "-n", help="Number of trailing lines to show."),
    follow: bool = typer.Option(False, "--follow", "-f", help="Stream new lines until interrupted."),
    json_output: bool = typer.Option(False, "--json", help="Emit each line as a JSON record."),
) -> None:
    """Print the tail of the bot's log; ``-f`` streams new lines as they are written."""
    instance = Instance(name)
    if not instance.exists():
        fail(f"instance '{name}' not found", ExitCode.NOT_FOUND, json_output=json_output)

    log_file = _resolve_log_file(instance)
    if log_file is None:
        fail(f"no log file for '{name}' yet", ExitCode.ERROR, json_output=json_output)

    def emit(line: str) -> None:
        line = line.rstrip("\n")
        if json_output:
            print_json({"name": name, "line": line})
        else:
            typer.echo(line)

    with open(log_file, "r", errors="replace") as f:
        tail = f.readlines()[-lines:]
        for line in tail:
            emit(line)
        if not follow:
            return
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
