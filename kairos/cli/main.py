"""``hbot`` CLI entrypoint — run, control, and monitor Kairos-2 bots.

Designed to be driven non-interactively by agentic harnesses: every command emits compact Markdown
and returns a stable exit code (see ``kairos.cli.output.ExitCode``); the run/observe commands
(deploy/start/stop/status/logs/config/balance) also take ``--json`` for machine-readable output.
One bot per install (like Kairos-2 itself); for multiple bots, use multiple installs/containers.
"""
from pathlib import Path
from typing import Optional

import typer

from kairos.cli.commands import (
    balance as balance_cmd,
    config as config_cmd,
    connect as connect_cmd,
    create as create_cmd,
    deploy as deploy_cmd,
    doctor as doctor_cmd,
    history as history_cmd,
    import_cmd,
    logs as logs_cmd,
    start as start_cmd,
    status as status_cmd,
    stop as stop_cmd,
    update as update_cmd,
)
from kairos.cli.output import SortedCommandsGroup

app = typer.Typer(
    name="hbot",
    cls=SortedCommandsGroup,
    no_args_is_help=True,
    add_completion=False,
    help="Run, control, and monitor a Kairos-2 bot (one bot per install).",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version() -> str:
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    try:
        return version_file.read_text().strip()
    except OSError:
        return "unknown"


@app.callback(invoke_without_command=True)
def _root(
    version: Optional[bool] = typer.Option(
        None, "--version", help="Show the hbot/Kairos-2 version and exit.", is_eager=True),
) -> None:
    if version:
        typer.echo(f"hbot {_version()}")
        raise typer.Exit()


# v1 surface — a faithful subset of the interactive client's commands, plus one
# composite: `deploy` (= create/import + start in one call, the primitive agents reach for). Order
# here is irrelevant; --help lists them alphabetically (SortedCommandsGroup).
app.command("connect")(connect_cmd.connect)
app.command("balance")(balance_cmd.balance)
app.command("create")(create_cmd.create)
app.command("import")(import_cmd.import_config)
# ignore_unknown_options: config values can legitimately start with '-' (negative spreads/pcts);
# without it `hbot config <key> -1` dies at the parser with "No such option: -1". Known options
# (--json, -h) still parse; anything else option-shaped falls through to the VALUE argument.
app.command("config", context_settings={"ignore_unknown_options": True})(config_cmd.config)
app.command("deploy")(deploy_cmd.deploy)
app.command("start")(start_cmd.start)
app.command("stop")(stop_cmd.stop)
app.command("status")(status_cmd.status)
app.command("logs")(logs_cmd.logs)
app.command("history")(history_cmd.history)
app.command("update")(update_cmd.update)
app.command("doctor")(doctor_cmd.doctor)


def main() -> None:
    """Console-script entrypoint (``hbot``)."""
    app()


if __name__ == "__main__":
    main()
