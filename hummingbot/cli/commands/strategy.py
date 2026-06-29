"""``hbot strategy`` — discover strategies and create/browse/edit their config files.

Two layers:
  strategies (what you can create from)        configs (concrete files you run/edit)
  --------------------------------------       -------------------------------------
  hbot strategy list                           hbot strategy list-configs
  hbot strategy show <strategy>                hbot strategy show-config <file>
  hbot strategy create <strategy>              hbot strategy set <file> <key> <value>

`list`/`show` operate on strategy *types* (v1 strategies, v2 scripts, controllers). `list-configs`/
`show-config`/`set` operate on the `.yml` config files. To live-tune a RUNNING bot use `hbot update`.
"""
from pathlib import Path
from typing import List, Optional

import typer

from hummingbot.cli.output import ExitCode, SortedCommandsGroup, fail, print_json

strategy_app = typer.Typer(
    cls=SortedCommandsGroup, no_args_is_help=True,
    help="Discover strategies and create/edit their config files.")


def _one_type(v1: bool, v2: bool, controller: bool, json_output: bool, required: bool) -> Optional[str]:
    chosen = [t for t, on in (("v1-strategy", v1), ("v2-script", v2), ("controller", controller)) if on]
    if len(chosen) > 1:
        fail("use only one of --v1-strategy / --v2-script / --controller", ExitCode.CONFIG_ERROR, json_output=json_output)
    if required and not chosen:
        fail("specify one of --v1-strategy / --v2-script / --controller", ExitCode.CONFIG_ERROR, json_output=json_output)
    return chosen[0] if chosen else None


def _disambiguate(name: str, matches: List[str], what: str, json_output: bool) -> str:
    """Turn a list of matching types into the single one, or fail clearly (none / collision)."""
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        fail(f"'{name}' exists as {' and '.join(matches)} — disambiguate with "
             f"{' / '.join('--' + m for m in matches)}", ExitCode.CONFIG_ERROR, json_output=json_output)
    fail(f"{what} '{name}' not found", ExitCode.NOT_FOUND, json_output=json_output)


def _resolve_strategy_type(name: str, v1: bool, v2: bool, controller: bool, json_output: bool) -> str:
    """Pick the strategy type: an explicit flag, else detect it from the name (v1/v2/controller names
    are assumed unique; a genuine cross-type collision needs a flag)."""
    from hummingbot.cli.strategy_configs import matching_strategy_types
    explicit = _one_type(v1, v2, controller, json_output, required=False)
    if explicit:
        return explicit
    return _disambiguate(name, matching_strategy_types(name), "strategy", json_output)


# --- strategies (creatable types) -------------------------------------------------------------

@strategy_app.command("list")
def list_cmd(
    v1: bool = typer.Option(False, "--v1-strategy"),
    v2: bool = typer.Option(False, "--v2-script"),
    controller: bool = typer.Option(False, "--controller"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List strategies available to create from (v1 strategies, v2 scripts, controllers)."""
    from hummingbot.cli.strategy_configs import STRATEGY_TYPES, available_sources
    stype = _one_type(v1, v2, controller, json_output, required=False)
    types: List[str] = [stype] if stype else list(STRATEGY_TYPES)
    catalog = {t: available_sources(t) for t in types}
    if json_output:
        print_json({"ok": True, "strategies": catalog})
    else:
        for t in types:
            typer.echo(f"\n{t}:")
            for name in catalog[t]:
                typer.echo(f"  {name}")


@strategy_app.command("show")
def show_cmd(
    strategy: str = typer.Argument(..., help="Strategy/controller/script name."),
    v1: bool = typer.Option(False, "--v1-strategy"),
    v2: bool = typer.Option(False, "--v2-script"),
    controller: bool = typer.Option(False, "--controller"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show a strategy's fields: defaults, required (to fill), and live (controller-updatable)."""
    from hummingbot.cli.strategy_configs import describe_strategy
    stype = _resolve_strategy_type(strategy, v1, v2, controller, json_output)
    try:
        # show is read-only preview: don't mint a real controller id (would look meaningful but isn't).
        data, required, updatable = describe_strategy(stype, strategy, scaffold_id=False)
    except Exception as e:
        fail(str(e), ExitCode.CONFIG_ERROR, json_output=json_output)
    if json_output:
        print_json({"ok": True, "type": stype, "strategy": strategy,
                    "required": required, "live_fields": sorted(updatable), "fields": data})
    else:
        typer.echo(f"{stype}: {strategy}")
        for k, val in data.items():
            marks = "".join([" (required)" if k in required else "", " (live)" if k in updatable else ""])
            typer.echo(f"  {k} = {val}{marks}")


_START_FLAG = {"v1-strategy": "--v1-strategy", "v2-script": "--v2-script", "controller": "--controller"}


def _collect_values(set_values: Optional[List[str]], values_stdin: bool, json_output: bool) -> dict:
    """Merge field values from --set pairs and/or a JSON object on stdin (stdin first, --set wins)."""
    from hummingbot.cli.strategy_configs import parse_set_pairs
    values: dict = {}
    if values_stdin:
        import json
        import sys
        raw = sys.stdin.read()
        try:
            parsed = json.loads(raw) if raw.strip() else {}
        except Exception as e:
            fail(f"--values-stdin: invalid JSON: {e}", ExitCode.CONFIG_ERROR, json_output=json_output)
        if not isinstance(parsed, dict):
            fail("--values-stdin: expected a JSON object of field:value", ExitCode.CONFIG_ERROR, json_output=json_output)
        values.update(parsed)
    if set_values:
        try:
            values.update(parse_set_pairs(set_values))
        except ValueError as e:
            fail(str(e), ExitCode.CONFIG_ERROR, json_output=json_output)
    return values


@strategy_app.command("create")
def create_cmd(
    strategy: str = typer.Argument(..., help="Strategy/controller/script name to scaffold from."),
    v1: bool = typer.Option(False, "--v1-strategy"),
    v2: bool = typer.Option(False, "--v2-script"),
    controller: bool = typer.Option(False, "--controller"),
    name: Optional[str] = typer.Option(None, "--name", help="Output config file name (default: a free conf_<strategy>.yml)."),
    set_values: Optional[List[str]] = typer.Option(
        None, "--set", help="Fill a field inline: --set key=value (repeatable). Fill the required fields here to create a ready-to-run config in one call."),
    values_stdin: bool = typer.Option(
        False, "--values-stdin", help="Read a JSON object {field: value} from stdin and apply it (bulk fill; pairs with `strategy show --json`)."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Scaffold a new config from a strategy's defaults, optionally filling fields inline.

    Agent-friendly: `--set k=v` (repeatable) or `--values-stdin` populate fields in the same call, so a
    fully-specified config is created and validated at once instead of one `set` round-trip per field.
    """
    from hummingbot.cli.strategy_configs import (
        create_config_file,
        describe_strategy,
        fill_template,
        matching_config_types,
        normalize_config_name,
        suggest_free_name,
    )
    stype = _resolve_strategy_type(strategy, v1, v2, controller, json_output)
    try:
        data, required, _ = describe_strategy(stype, strategy)
    except Exception as e:
        fail(str(e), ExitCode.CONFIG_ERROR, json_output=json_output)

    values = _collect_values(set_values, values_stdin, json_output)
    # A controller's id is always generated by the scaffold; ignore any user-supplied one (e.g. piping
    # `show --json`, whose id is a placeholder) so we never persist a bogus/duplicate id.
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
                 f"be unique across types. Try --name {suggestion}", ExitCode.CONFIG_ERROR, json_output=json_output)
        out_name = suggestion

    try:
        remaining = fill_template(data, required, stype, values)
    except Exception as e:
        fail(f"invalid field value: {e}", ExitCode.CONFIG_ERROR, json_output=json_output)

    try:
        create_config_file(stype, out_name, data)
    except FileExistsError as e:
        fail(str(e), ExitCode.CONFIG_ERROR, json_output=json_output)

    ready = not remaining
    if json_output:
        print_json({"ok": True, "type": stype, "file": out_name, "applied": sorted(values),
                    "required_remaining": remaining, "ready": ready})
    else:
        typer.echo(f"Created {stype}/{out_name}")
        if remaining:
            typer.echo(f"Fill required fields: {', '.join(remaining)}")
            typer.echo(f"  e.g. hbot strategy set {out_name} {remaining[0]} <value>")
        else:
            typer.echo(f"Ready to start: hbot start {out_name} {_START_FLAG[stype]}")


@strategy_app.command("clone")
def clone_cmd(
    source: str = typer.Argument(..., help="Existing config file to clone from."),
    v1: bool = typer.Option(False, "--v1-strategy"),
    v2: bool = typer.Option(False, "--v2-script"),
    controller: bool = typer.Option(False, "--controller"),
    name: Optional[str] = typer.Option(None, "--name", help="New config file name (default: a free copy of the source name)."),
    set_values: Optional[List[str]] = typer.Option(
        None, "--set", help="Change a field in the clone: --set key=value (repeatable)."),
    values_stdin: bool = typer.Option(
        False, "--values-stdin", help="Read a JSON object {field: value} from stdin and apply it to the clone."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Copy an existing config to a new name (comments preserved), optionally changing fields.

    Unlike `create` (which scaffolds a strategy's defaults), `clone` starts from a config you already
    filled in. A cloned controller gets a fresh id so it doesn't collide with the original when run.
    """
    from hummingbot.cli.strategy_configs import (
        clone_config,
        matching_config_types,
        normalize_config_name,
        suggest_free_name,
    )
    stype = _resolve(_one_type(v1, v2, controller, json_output, required=False), source, json_output)

    values = _collect_values(set_values, values_stdin, json_output)
    if stype == "controller":
        values.pop("id", None)  # the clone always gets a freshly minted id

    out_name = normalize_config_name(name or source)
    collisions = matching_config_types(out_name)
    if collisions:
        suggestion = suggest_free_name(out_name)
        if name:
            fail(f"'{out_name}' already exists as a {' and '.join(collisions)} config — config names must "
                 f"be unique across types. Try --name {suggestion}", ExitCode.CONFIG_ERROR, json_output=json_output)
        out_name = suggestion  # default name == source, so roll forward to the next free name

    try:
        new_id = clone_config(stype, source, out_name, values)
    except Exception as e:
        fail(f"clone failed: {e}", ExitCode.CONFIG_ERROR, json_output=json_output)

    if json_output:
        print_json({"ok": True, "type": stype, "source": source, "file": out_name,
                    "applied": sorted(values), "new_id": new_id})
    else:
        typer.echo(f"Cloned {stype}/{source} → {out_name}")
        if values:
            typer.echo(f"Changed: {', '.join(sorted(values))}")
        typer.echo(f"Ready to start: hbot start {out_name} {_START_FLAG[stype]}")


# --- configs (concrete files) -----------------------------------------------------------------

def _resolve(stype: Optional[str], file: str, json_output: bool) -> str:
    """Resolve a config file's type: an explicit flag, else which conf dir holds it."""
    from hummingbot.cli.strategy_configs import config_path, matching_config_types
    if stype is not None:
        if not config_path(stype, file).exists():
            fail(f"{stype} config not found: {file}", ExitCode.NOT_FOUND, json_output=json_output)
        return stype
    return _disambiguate(file, matching_config_types(file), "config", json_output)


@strategy_app.command("list-configs")
def list_configs_cmd(
    v1: bool = typer.Option(False, "--v1-strategy"),
    v2: bool = typer.Option(False, "--v2-script"),
    controller: bool = typer.Option(False, "--controller"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List existing config files (all types, or one)."""
    from hummingbot.cli.strategy_configs import STRATEGY_TYPES, list_configs
    stype = _one_type(v1, v2, controller, json_output, required=False)
    types: List[str] = [stype] if stype else list(STRATEGY_TYPES)
    listing = {t: list_configs(t) for t in types}
    if json_output:
        print_json({"ok": True, "configs": listing})
    else:
        for t in types:
            typer.echo(f"\n{t}:")
            for name in listing[t]:
                typer.echo(f"  {name}")


@strategy_app.command("show-config")
def show_config_cmd(
    file: str = typer.Argument(..., help="Config file name."),
    v1: bool = typer.Option(False, "--v1-strategy"),
    v2: bool = typer.Option(False, "--v2-script"),
    controller: bool = typer.Option(False, "--controller"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show a config file (controller fields that apply live are marked)."""
    from hummingbot.cli.strategy_configs import config_path, read_yaml, updatable_for
    stype = _resolve(_one_type(v1, v2, controller, json_output, required=False), file, json_output)
    path = config_path(stype, file)
    data = read_yaml(path)
    updatable = updatable_for(stype, path)
    if json_output:
        print_json({"ok": True, "type": stype, "file": file,
                    "updatable_fields": sorted(updatable), "config": data})
    else:
        typer.echo(f"{stype}: {file}")
        for k, val in data.items():
            typer.echo(f"  {k} = {val}{'  (live)' if k in updatable else ''}")


@strategy_app.command("set")
def set_cmd(
    file: str = typer.Argument(..., help="Config file name."),
    key: str = typer.Argument(..., help="Field key (dotted)."),
    value: str = typer.Argument(..., help="New value."),
    v1: bool = typer.Option(False, "--v1-strategy"),
    v2: bool = typer.Option(False, "--v2-script"),
    controller: bool = typer.Option(False, "--controller"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Edit a field in a config file (validated for controllers; comments preserved)."""
    from hummingbot.cli.strategy_configs import config_path, edit_config
    stype = _resolve(_one_type(v1, v2, controller, json_output, required=False), file, json_output)
    path = config_path(stype, file)
    try:
        new_value, _ = edit_config(path, stype, key, value)
    except KeyError:
        fail(f"key '{key}' not found in {file}", ExitCode.CONFIG_ERROR, json_output=json_output)
    except Exception as e:
        fail(f"value rejected: {e}", ExitCode.CONFIG_ERROR, json_output=json_output)
    if json_output:
        print_json({"ok": True, "type": stype, "file": file, "key": key, "value": new_value})
    else:
        typer.echo(f"{key} = {new_value}  (saved to {stype}/{file})")
