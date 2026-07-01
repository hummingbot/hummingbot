"""``hbot create`` — create a strategy config file from a strategy / controller / script.

Mirrors the interactive client's ``create`` (which prompts field-by-field), but non-interactively —
fields are supplied up front, so one call produces a config. Two ways to fill it:

* **one-shot** (agents): give every required field with ``--set key=value`` (repeatable) or a JSON
  object on stdin via ``--values-stdin`` → a validated, ready-to-run config. A missing required field
  fails and lists exactly what's needed (which doubles as field discovery).
* **scaffold** (humans): ``--with-defaults`` writes the template's defaults and leaves required fields
  blank, so ``create`` never blocks on inputs. Finish it with ``hbot config``, then ``hbot start``.

The strategy's type (``v1-strategy`` / ``v2-script`` / ``controller``) is auto-detected from its name;
a ``--v1-strategy`` / ``--v2-script`` / ``--controller`` flag is only needed for a name that exists
under more than one. The created config is **loaded** (like ``hbot import``), so ``hbot config`` shows
it and ``hbot start`` with no argument runs it.
"""
from pathlib import Path
from typing import List, Optional

import typer

from hummingbot.cli import bot
from hummingbot.cli.commands._common import one_type, read_json_object_from_stdin
from hummingbot.cli.output import ExitCode, echo, fail, render_kv


def _resolve_strategy_type(strategy: str, v1: bool, v2: bool, controller: bool) -> str:
    """Pick the strategy's type: an explicit flag, else detect from the name. Fails clearly on a
    cross-type collision, and on "not found" lists what IS available (name discovery)."""
    from hummingbot.cli.strategy_configs import STRATEGY_TYPES, available_sources, matching_strategy_types
    explicit = one_type(v1, v2, controller, required=False)
    if explicit:
        return explicit
    matches = matching_strategy_types(strategy)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        fail(f"'{strategy}' exists as {' and '.join(matches)} — disambiguate with "
             f"{' / '.join('--' + m for m in matches)}", ExitCode.CONFIG_ERROR)
    avail = {t: available_sources(t) for t in STRATEGY_TYPES}
    hint = "; ".join(f"{t}: {', '.join(avail[t][:8])}{' …' if len(avail[t]) > 8 else ''}"
                     for t in STRATEGY_TYPES if avail[t])
    fail(f"strategy '{strategy}' not found. Available — {hint}", ExitCode.NOT_FOUND)


def _collect_values(set_values: Optional[List[str]], values_stdin: bool) -> dict:
    """Merge field values from --set pairs and/or a JSON object on stdin (stdin first, --set wins)."""
    from hummingbot.cli.strategy_configs import parse_set_pairs
    values: dict = {}
    if values_stdin:
        values.update(read_json_object_from_stdin())
    if set_values:
        try:
            values.update(parse_set_pairs(set_values))
        except ValueError as e:
            fail(str(e), ExitCode.CONFIG_ERROR)
    return values


def create(
    strategy: str = typer.Argument(..., help="Strategy / controller / script to create a config from (e.g. pmm_simple)."),
    set_values: Optional[List[str]] = typer.Option(
        None, "--set", help="Fill a field inline: --set key=value (repeatable). Supply the required fields here for a ready-to-run config."),
    values_stdin: bool = typer.Option(
        False, "--values-stdin", help="Read a JSON object {field: value} from stdin and apply it (bulk fill)."),
    with_defaults: bool = typer.Option(
        False, "--with-defaults", help="Scaffold with template defaults and leave required fields blank (fill later via `hbot config`), instead of requiring them now."),
    name: Optional[str] = typer.Option(
        None, "--name", help="Output config file name (default: a free conf_<strategy>.yml)."),
    v1: bool = typer.Option(False, "--v1-strategy", help="Force V1 strategy type (only if the name collides across types)."),
    v2: bool = typer.Option(False, "--v2-script", help="Force V2 script type (only if the name collides across types)."),
    controller: bool = typer.Option(
        False, "--controller", help="Force controller type (only if the name collides across types)."),
) -> None:
    """Create a strategy config file, then load it (for `config` / `start`)."""
    record = create_config(strategy=strategy, set_values=set_values, values_stdin=values_stdin,
                           with_defaults=with_defaults, name=name, v1=v1, v2=v2, controller=controller)
    echo(render_kv(record, title=f"created {record['type']}/{record['file']}"))


def create_config(*, strategy: str, set_values: Optional[List[str]] = None, values_stdin: bool = False,
                  with_defaults: bool = False, name: Optional[str] = None,
                  v1: bool = False, v2: bool = False, controller: bool = False) -> dict:
    """The core of ``hbot create`` — scaffold, fill, validate, write, load; returns the record.

    Shared with ``hbot deploy`` (which bundles config creation + launch into one call).
    """
    from hummingbot.cli.strategy_configs import (
        create_config_file,
        describe_strategy,
        fill_template,
        matching_config_types,
        normalize_config_name,
        suggest_free_name,
    )
    stype = _resolve_strategy_type(strategy, v1, v2, controller)
    try:
        data, required, _ = describe_strategy(stype, strategy)
    except Exception as e:
        fail(str(e), ExitCode.CONFIG_ERROR)

    values = _collect_values(set_values, values_stdin)
    # A controller's id is always scaffold-generated; ignore any user-supplied one.
    if stype == "controller":
        values.pop("id", None)

    # Names are unique across types. An explicit colliding --name is a hard error (with a suggestion);
    # the default name silently rolls forward to the next free conf_<strategy>_N.yml.
    out_name = normalize_config_name(name or f"conf_{Path(strategy).stem}.yml")
    collisions = matching_config_types(out_name)
    if collisions:
        suggestion = suggest_free_name(out_name)
        if name:
            fail(f"'{out_name}' already exists as a {' and '.join(collisions)} config — config names must "
                 f"be unique across types. Try --name {suggestion}", ExitCode.CONFIG_ERROR)
        out_name = suggestion

    try:
        remaining = fill_template(data, required, stype, values)
    except Exception as e:
        fail(f"invalid field value: {e}", ExitCode.CONFIG_ERROR)

    # Strict by default: a create yields a ready-to-run config, or nothing. --with-defaults relaxes
    # this to a scaffold you finish with `hbot config` — so `create` never has to block on inputs.
    if remaining and not with_defaults:
        fail(f"missing required fields: {', '.join(remaining)}. Supply them with --set key=value "
             f"(or --values-stdin), or pass --with-defaults to scaffold and fill later with `hbot config`",
             ExitCode.CONFIG_ERROR)

    try:
        create_config_file(stype, out_name, data)
    except FileExistsError as e:
        fail(str(e), ExitCode.CONFIG_ERROR)

    # Load it (like `hbot import`): `hbot config` shows it, `hbot start` with no argument runs it.
    bot.write_loaded(out_name, stype)

    record = {"file": out_name, "type": stype, "applied": ", ".join(sorted(values)) or "-",
              "ready": not remaining}
    if remaining:
        record["required_remaining"] = ", ".join(remaining)
        record["next"] = f"hbot config {remaining[0]} <value>"
    else:
        record["next"] = "hbot start"
    return record
