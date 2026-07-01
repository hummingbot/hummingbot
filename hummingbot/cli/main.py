"""``hbot`` CLI entrypoint — run, control, and monitor Hummingbot bots.

Designed to be driven non-interactively by agentic harnesses: every command emits compact Markdown
and returns a stable exit code (see ``hummingbot.cli.output.ExitCode``); the run/observe commands
(deploy/start/stop/status/logs/config/balance) also take ``--json`` for machine-readable output.
One bot per install (like Hummingbot itself); for multiple bots, use multiple installs/containers.
"""
from pathlib import Path
from typing import Optional

import typer

from hummingbot.cli.commands import (
    balance as balance_cmd,
    config as config_cmd,
    connect as connect_cmd,
    create as create_cmd,
    deploy as deploy_cmd,
    history as history_cmd,
    import_cmd,
    logs as logs_cmd,
    rate as rate_cmd,
    start as start_cmd,
    status as status_cmd,
    stop as stop_cmd,
    ticker as ticker_cmd,
    update as update_cmd,
)
from hummingbot.cli.output import SortedCommandsGroup

app = typer.Typer(
    name="hbot",
    cls=SortedCommandsGroup,
    no_args_is_help=True,
    add_completion=False,
    help="Run, control, and monitor a Hummingbot bot (one bot per install).",
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
        None, "--version", help="Show the hbot/Hummingbot version and exit.", is_eager=True),
) -> None:
    if version:
        typer.echo(f"hbot {_version()}")
        raise typer.Exit()


# v1 surface — a faithful subset of the interactive client's commands (minus gateway), plus one
# composite: `deploy` (= create/import + start in one call, the primitive agents reach for). Order
# here is irrelevant; --help lists them alphabetically (SortedCommandsGroup).
app.command("connect")(connect_cmd.connect)
app.command("balance")(balance_cmd.balance)
app.command("ticker")(ticker_cmd.ticker)
app.command("rate")(rate_cmd.rate)
app.command("create")(create_cmd.create)
app.command("import")(import_cmd.import_config)
app.command("config")(config_cmd.config)
app.command("update")(update_cmd.update)
app.command("deploy")(deploy_cmd.deploy)
app.command("start")(start_cmd.start)
app.command("stop")(stop_cmd.stop)
app.command("status")(status_cmd.status)
app.command("logs")(logs_cmd.logs)
app.command("history")(history_cmd.history)


def main() -> None:
    """Console-script entrypoint (``hbot``)."""
    app()


if __name__ == "__main__":
    main()
