"""``hbot deploy`` — one-shot "config → running bot" (create-or-import + start, bundled).

The high-level primitive an agent wants: one command that goes from a strategy (or an existing
config file) to a bot placing orders. It is exactly ``create``/``import`` followed by ``start`` —
no new semantics, just one call instead of two:

* ``hbot deploy conf_eth.yml``            — an existing config file → validate, load, start
* ``hbot deploy conf_eth.yml --set total_amount_quote=500``  — edit it first (comment-preserving)
* ``hbot deploy pmm_simple --set connector_name=... --set trading_pair=...`` — a strategy name →
  create a ready-to-run config (every required field must be supplied, like ``create``), then start.

The target is resolved config-file-first: a name that matches an existing config in
``conf/strategies|scripts|controllers`` deploys that file; otherwise it must name a creatable
strategy / controller / script. Everything else (readiness wait, --replace, --foreground,
password handling, exit codes) is ``hbot start``'s behavior, unchanged.
"""
from typing import List, Optional, Tuple

import typer

from hummingbot.cli import bot
from hummingbot.cli.commands._common import one_type
from hummingbot.cli.output import ExitCode, emit, fail, json_option, render_kv


def resolve_target(target: str, explicit_type: Optional[str]) -> Tuple[str, str, Optional[str]]:
    """Resolve what ``target`` names: ``("config", filename, stype)`` for an existing config file,
    else ``("strategy", target, None)`` for a creatable strategy/controller/script.

    Config files win (they are unique across types); a name that is neither fails NOT_FOUND.
    """
    from hummingbot.cli.strategy_configs import (
        matching_config_types,
        matching_strategy_types,
        normalize_config_name,
        resolve_config_type,
    )
    fname = normalize_config_name(target)
    if matching_config_types(fname):
        try:
            return "config", fname, resolve_config_type(fname, explicit_type)
        except (FileNotFoundError, ValueError) as e:
            fail(str(e), ExitCode.CONFIG_ERROR)
    if explicit_type or matching_strategy_types(target):
        return "strategy", target, None
    fail(f"'{target}' is neither an existing config file nor a creatable strategy — "
         f"run `hbot create <strategy>` for name discovery, or `hbot import <file>` for configs",
         ExitCode.NOT_FOUND)


def deploy(
    target: str = typer.Argument(
        ..., help="An existing config file (conf/strategies|scripts|controllers), or a strategy / controller / script name to create one from."),
    set_values: Optional[List[str]] = typer.Option(
        None, "--set", help="Set a field before launch: --set key=value (repeatable). Creating: fills required fields. Existing config: edits it (comment-preserving)."),
    values_stdin: bool = typer.Option(
        False, "--values-stdin", help="Read a JSON object {field: value} from stdin and apply it (bulk fill)."),
    name: Optional[str] = typer.Option(
        None, "--name", help="Config file name when creating (default: a free conf_<strategy>.yml)."),
    v1: bool = typer.Option(False, "--v1-strategy", help="Force V1 strategy type (only if the name collides across types)."),
    v2: bool = typer.Option(False, "--v2-script", help="Force V2 script type (only if the name collides across types)."),
    controller: bool = typer.Option(
        False, "--controller", help="Force controller type (only if the name collides across types)."),
    replace: bool = typer.Option(
        False, "--replace", help="If a bot is already running, stop it first, then start this one."),
    foreground: bool = typer.Option(
        False, "--foreground", help="Run the bot in the foreground (use as a container's main process)."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
    timeout: float = typer.Option(120.0, "--timeout", help="Seconds to wait for the bot to start."),
    as_json: bool = json_option(),
) -> None:
    """Deploy in one shot: create/load a config and start the bot."""
    from hummingbot.cli.commands.create import create_config
    from hummingbot.cli.commands.start import launch
    from hummingbot.cli.strategy_configs import config_path, edit_config, parse_set_pairs, validate_controller

    explicit_type = one_type(v1, v2, controller, required=False)
    kind, resolved, stype = resolve_target(target, explicit_type)

    if kind == "config":
        if name:
            fail("--name only applies when creating from a strategy; "
                 f"'{resolved}' is an existing config", ExitCode.CONFIG_ERROR)
        # Apply --set / stdin edits to the existing file (comment-preserving; controllers validated).
        values: dict = {}
        if values_stdin:
            from hummingbot.cli.commands._common import read_json_object_from_stdin
            values.update(read_json_object_from_stdin())
        if set_values:
            try:
                values.update(parse_set_pairs(set_values))
            except ValueError as e:
                fail(str(e), ExitCode.CONFIG_ERROR)
        path = config_path(stype, resolved)
        for key, value in values.items():
            try:
                edit_config(path, stype, key, str(value))
            except KeyError:
                fail(f"key '{key}' not found in {resolved}", ExitCode.CONFIG_ERROR)
            except Exception as e:
                fail(f"value rejected for '{key}': {e}", ExitCode.CONFIG_ERROR)
        if stype == "controller":
            try:
                validate_controller(path)  # a broken controller fails here, not mid-launch
            except Exception as e:
                fail(f"invalid controller config: {e}", ExitCode.CONFIG_ERROR)
        bot.write_loaded(resolved, stype)
        config_record = {"file": resolved, "type": stype, "config": "existing",
                         "applied": ", ".join(sorted(values)) or "-"}
    else:
        # Strict like `create` without --with-defaults: every required field must be supplied,
        # because deploy's contract is a RUNNING bot — a scaffold can't run.
        created = create_config(strategy=resolved, set_values=set_values, values_stdin=values_stdin,
                                with_defaults=False, name=name, v1=v1, v2=v2, controller=controller)
        config_record = {"file": created["file"], "type": created["type"], "config": "created",
                         "applied": created["applied"]}

    started = launch(file=config_record["file"], v1=config_record["type"] == "v1-strategy",
                     v2=config_record["type"] == "v2-script",
                     controller=config_record["type"] == "controller",
                     replace=replace, foreground=foreground, password_stdin=password_stdin,
                     timeout=timeout)

    record = {**config_record, **started}
    emit(record, render_kv(record, title=f"deployed {record['file']}"), as_json)
