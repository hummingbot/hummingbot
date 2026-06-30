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

from hummingbot.cli.commands._common import one_type as _one_type, read_json_object_from_stdin
from hummingbot.cli.output import ExitCode, SortedCommandsGroup, cell, echo, fail, render_kv, render_table

strategy_app = typer.Typer(
    cls=SortedCommandsGroup, no_args_is_help=True,
    help="Browse strategies and build their config files.")


def _disambiguate(name: str, matches: List[str], what: str) -> str:
    """Turn a list of matching types into the single one, or fail clearly (none / collision)."""
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        fail(f"'{name}' exists as {' and '.join(matches)} — disambiguate with "
             f"{' / '.join('--' + m for m in matches)}", ExitCode.CONFIG_ERROR)
    fail(f"{what} '{name}' not found", ExitCode.NOT_FOUND)


def _resolve_strategy_type(name: str, v1: bool, v2: bool, controller: bool) -> str:
    """Pick the strategy type: an explicit flag, else detect it from the name (v1/v2/controller names
    are assumed unique; a genuine cross-type collision needs a flag)."""
    from hummingbot.cli.strategy_configs import matching_strategy_types
    explicit = _one_type(v1, v2, controller, required=False)
    if explicit:
        return explicit
    return _disambiguate(name, matching_strategy_types(name), "strategy")


# --- strategies (creatable types) -------------------------------------------------------------

@strategy_app.command("list")
def list_cmd(
    v1: bool = typer.Option(False, "--v1-strategy"),
    v2: bool = typer.Option(False, "--v2-script"),
    controller: bool = typer.Option(False, "--controller"),
) -> None:
    """List the strategies you can create configs from."""
    from hummingbot.cli.strategy_configs import STRATEGY_TYPES, available_sources
    stype = _one_type(v1, v2, controller, required=False)
    types: List[str] = [stype] if stype else list(STRATEGY_TYPES)
    rows = [{"type": t, "strategy": name} for t in types for name in available_sources(t)]
    echo(render_table(rows, columns=["type", "strategy"], title="strategies"))


@strategy_app.command("show")
def show_cmd(
    strategy: str = typer.Argument(..., help="Strategy/controller/script name."),
    v1: bool = typer.Option(False, "--v1-strategy"),
    v2: bool = typer.Option(False, "--v2-script"),
    controller: bool = typer.Option(False, "--controller"),
) -> None:
    """Show a strategy's fields and which ones you must fill in."""
    from hummingbot.cli.strategy_configs import describe_strategy
    stype = _resolve_strategy_type(strategy, v1, v2, controller)
    try:
        # show is read-only preview: don't mint a real controller id (would look meaningful but isn't).
        data, required, updatable = describe_strategy(stype, strategy, scaffold_id=False)
    except Exception as e:
        fail(str(e), ExitCode.CONFIG_ERROR)
    # The framework = the source folder this lives in: controllers/<type> for a controller,
    # scripts/ for a v2 script, hummingbot/strategy/<name>/ for a v1 strategy.
    framework = {
        "controller": f"controllers/{data.get('controller_type', '')}".rstrip("/"),
        "v2-script": "scripts",
        "v1-strategy": f"hummingbot/strategy/{strategy}",
    }[stype]
    rows = [{"field": k, "value": cell(val), "required": k in required, "live": k in updatable}
            for k, val in data.items()]
    header = render_kv({"type": stype, "framework": framework}, title=strategy)
    echo(header + "\n\n" + render_table(rows, columns=["field", "value", "required", "live"]))


_START_FLAG = {"v1-strategy": "--v1-strategy", "v2-script": "--v2-script", "controller": "--controller"}


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
        False, "--values-stdin", help="Read a JSON object {field: value} from stdin and apply it (bulk fill; pairs with `strategy show`)."),
) -> None:
    """Create a config from a strategy, optionally filling in fields.

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
    stype = _resolve_strategy_type(strategy, v1, v2, controller)
    try:
        data, required, _ = describe_strategy(stype, strategy)
    except Exception as e:
        fail(str(e), ExitCode.CONFIG_ERROR)

    values = _collect_values(set_values, values_stdin)
    # A controller's id is always generated by the scaffold; ignore any user-supplied one (e.g. piping
    # `show`, whose id is a placeholder) so we never persist a bogus/duplicate id.
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

    try:
        create_config_file(stype, out_name, data)
    except FileExistsError as e:
        fail(str(e), ExitCode.CONFIG_ERROR)

    record = {"type": stype, "file": out_name, "applied": ", ".join(sorted(values)),
              "ready": not remaining}
    if remaining:
        record["required_remaining"] = ", ".join(remaining)
        record["next"] = f"hbot strategy set {out_name} {remaining[0]} <value>"
    else:
        record["next"] = f"hbot start {out_name} {_START_FLAG[stype]}"
    echo(render_kv(record, title=f"created {stype}/{out_name}"))


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
) -> None:
    """Copy a config to a new name, optionally changing fields.

    Unlike `create` (which scaffolds a strategy's defaults), `clone` starts from a config you already
    filled in. A cloned controller gets a fresh id so it doesn't collide with the original when run.
    """
    from hummingbot.cli.strategy_configs import (
        clone_config,
        matching_config_types,
        normalize_config_name,
        suggest_free_name,
    )
    stype = _resolve(_one_type(v1, v2, controller, required=False), source)

    values = _collect_values(set_values, values_stdin)
    if stype == "controller":
        values.pop("id", None)  # the clone always gets a freshly minted id

    out_name = normalize_config_name(name or source)
    collisions = matching_config_types(out_name)
    if collisions:
        suggestion = suggest_free_name(out_name)
        if name:
            fail(f"'{out_name}' already exists as a {' and '.join(collisions)} config — config names must "
                 f"be unique across types. Try --name {suggestion}", ExitCode.CONFIG_ERROR)
        out_name = suggestion  # default name == source, so roll forward to the next free name

    try:
        new_id = clone_config(stype, source, out_name, values)
    except Exception as e:
        fail(f"clone failed: {e}", ExitCode.CONFIG_ERROR)

    record = {"type": stype, "source": source, "file": out_name,
              "changed": ", ".join(sorted(values)), "new_id": new_id,
              "next": f"hbot start {out_name} {_START_FLAG[stype]}"}
    echo(render_kv(record, title=f"cloned {stype}/{source} -> {out_name}"))


# --- configs (concrete files) -----------------------------------------------------------------

def _resolve(stype: Optional[str], file: str) -> str:
    """Resolve a config file's type: an explicit flag, else which conf dir holds it. Thin fail()-mapper
    over the shared ``resolve_config_type`` so every filename command resolves types identically."""
    from hummingbot.cli.strategy_configs import resolve_config_type
    try:
        return resolve_config_type(file, stype)
    except FileNotFoundError as e:
        fail(str(e), ExitCode.NOT_FOUND)
    except ValueError as e:
        fail(str(e), ExitCode.CONFIG_ERROR)


@strategy_app.command("list-configs")
def list_configs_cmd(
    v1: bool = typer.Option(False, "--v1-strategy"),
    v2: bool = typer.Option(False, "--v2-script"),
    controller: bool = typer.Option(False, "--controller"),
) -> None:
    """List your saved config files."""
    from hummingbot.cli.strategy_configs import STRATEGY_TYPES, list_configs
    stype = _one_type(v1, v2, controller, required=False)
    types: List[str] = [stype] if stype else list(STRATEGY_TYPES)
    rows = [{"type": t, "config": name} for t in types for name in list_configs(t)]
    echo(render_table(rows, columns=["type", "config"], title="configs"))


@strategy_app.command("show-config")
def show_config_cmd(
    file: str = typer.Argument(..., help="Config file name."),
    v1: bool = typer.Option(False, "--v1-strategy"),
    v2: bool = typer.Option(False, "--v2-script"),
    controller: bool = typer.Option(False, "--controller"),
) -> None:
    """Show the contents of a config file."""
    from hummingbot.cli.strategy_configs import config_path, read_yaml, updatable_for
    stype = _resolve(_one_type(v1, v2, controller, required=False), file)
    path = config_path(stype, file)
    data = read_yaml(path)
    updatable = updatable_for(stype, path)
    rows = [{"field": k, "value": cell(val), "live": k in updatable} for k, val in data.items()]
    echo(render_table(rows, columns=["field", "value", "live"], title=f"{stype}: {file}"))


@strategy_app.command("set")
def set_cmd(
    file: str = typer.Argument(..., help="Config file name."),
    key: str = typer.Argument(..., help="Field key (dotted)."),
    value: str = typer.Argument(..., help="New value."),
    v1: bool = typer.Option(False, "--v1-strategy"),
    v2: bool = typer.Option(False, "--v2-script"),
    controller: bool = typer.Option(False, "--controller"),
) -> None:
    """Change a field in a config file."""
    from hummingbot.cli.strategy_configs import config_path, edit_config
    stype = _resolve(_one_type(v1, v2, controller, required=False), file)
    path = config_path(stype, file)
    try:
        new_value, _ = edit_config(path, stype, key, value)
    except KeyError:
        fail(f"key '{key}' not found in {file}", ExitCode.CONFIG_ERROR)
    except Exception as e:
        fail(f"value rejected: {e}", ExitCode.CONFIG_ERROR)
    echo(render_kv({"key": key, "value": new_value, "saved_to": f"{stype}/{file}"},
                   title=f"set {file}"))
