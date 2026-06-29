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

from hummingbot.cli.output import ExitCode, fail, print_json

strategy_app = typer.Typer(no_args_is_help=True, help="Discover strategies and create/edit their config files.")


def _one_type(v1: bool, v2: bool, controller: bool, json_output: bool, required: bool) -> Optional[str]:
    chosen = [t for t, on in (("v1", v1), ("v2", v2), ("controller", controller)) if on]
    if len(chosen) > 1:
        fail("use only one of --v1 / --v2 / --controller", ExitCode.CONFIG_ERROR, json_output=json_output)
    if required and not chosen:
        fail("specify one of --v1 / --v2 / --controller", ExitCode.CONFIG_ERROR, json_output=json_output)
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
    v1: bool = typer.Option(False, "--v1"),
    v2: bool = typer.Option(False, "--v2"),
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
    v1: bool = typer.Option(False, "--v1"),
    v2: bool = typer.Option(False, "--v2"),
    controller: bool = typer.Option(False, "--controller"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show a strategy's fields: defaults, required (to fill), and live (controller-updatable)."""
    from hummingbot.cli.strategy_configs import describe_strategy
    stype = _resolve_strategy_type(strategy, v1, v2, controller, json_output)
    try:
        data, required, updatable = describe_strategy(stype, strategy)
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


@strategy_app.command("create")
def create_cmd(
    strategy: str = typer.Argument(..., help="Strategy/controller/script name to scaffold from."),
    v1: bool = typer.Option(False, "--v1"),
    v2: bool = typer.Option(False, "--v2"),
    controller: bool = typer.Option(False, "--controller"),
    name: Optional[str] = typer.Option(None, "--name", help="Output config file name."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Scaffold a new config from a strategy's defaults; lists fields you must fill."""
    from hummingbot.cli.strategy_configs import create_config_file, describe_strategy
    stype = _resolve_strategy_type(strategy, v1, v2, controller, json_output)
    try:
        data, required, _ = describe_strategy(stype, strategy)
    except Exception as e:
        fail(str(e), ExitCode.CONFIG_ERROR, json_output=json_output)

    out_name = name or f"conf_{Path(strategy).stem}_1.yml"
    try:
        create_config_file(stype, out_name, data)
    except FileExistsError as e:
        fail(str(e), ExitCode.CONFIG_ERROR, json_output=json_output)

    if json_output:
        print_json({"ok": True, "type": stype, "file": out_name, "required_fields": required})
    else:
        typer.echo(f"Created {stype}/{out_name}")
        if required:
            typer.echo(f"Fill required fields: {', '.join(required)}")
            typer.echo(f"  e.g. hbot strategy set {out_name} {required[0]} <value>")


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
    v1: bool = typer.Option(False, "--v1"),
    v2: bool = typer.Option(False, "--v2"),
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
    v1: bool = typer.Option(False, "--v1"),
    v2: bool = typer.Option(False, "--v2"),
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
    v1: bool = typer.Option(False, "--v1"),
    v2: bool = typer.Option(False, "--v2"),
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
