"""``hbot connect`` — list exchanges and securely store encrypted API keys.

Like Hummingbot's ``connect``: each exchange declares its own key fields (api key, secret, etc.).
Secrets are NEVER taken as flags. Supply them either interactively (hidden prompts) or, for
automation, as a JSON object on stdin (``--keys-stdin``). Keys are encrypted with the keystore
password via ``Security.update_secure_config`` and written to ``conf/connectors/<exchange>.yml``.
"""
import asyncio
import getpass
import json
import sys
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import typer

from hummingbot.cli.output import ExitCode, fail, print_json
from hummingbot.cli.password import login, resolve_password

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


def _connectable_exchanges() -> List[str]:
    from hummingbot.client.settings import AllConnectorSettings
    settings = AllConnectorSettings.get_connector_settings()
    return sorted(
        cs.name for cs in settings.values()
        if not cs.use_ethereum_wallet
        and not cs.uses_gateway_generic_connector()
        and cs.name != "probit_kr"
    )


def _connect_key_fields(cfg: "ClientConfigAdapter") -> List[Any]:
    return [item for item in cfg.traverse(secure=False)
            if item.client_field_data is not None and item.client_field_data.is_connect_key]


def _prompt_text(item: Any, cfg: "ClientConfigAdapter") -> str:
    prompt = item.client_field_data.prompt
    if callable(prompt):
        try:
            return prompt(cfg.hb_config)
        except Exception:
            return item.attr
    return prompt or item.attr


def _list_all(json_output: bool) -> None:
    """Static checklist of every connectable exchange (no password / network needed)."""
    from hummingbot.client.config.security import Security
    rows = [{"exchange": name, "keys_added": Security.connector_config_file_exists(name)}
            for name in _connectable_exchanges()]
    if json_output:
        print_json({"ok": True, "exchanges": rows})
        return
    for r in rows:
        typer.echo(f" [{'x' if r['keys_added'] else ' '}] {r['exchange']}")


def _show_connections(ccm, json_output: bool, password_stdin: bool) -> None:
    """Hummingbot-style ``connect`` table: tests the keys you've added and reports Keys Confirmed."""
    import pandas as pd

    from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
    from hummingbot.client.config.security import Security
    from hummingbot.client.ui.interface_utils import format_df_for_printout
    from hummingbot.user.user_balances import UserBalances
    keyed = [name for name in _connectable_exchanges() if Security.connector_config_file_exists(name)]
    if not keyed:
        if json_output:
            print_json({"ok": True, "connections": []})
        else:
            typer.echo("No exchanges connected. Run `hbot connect <exchange>` to add keys, "
                       "or `hbot connect --all` to list connectable exchanges.")
        return

    password = resolve_password(password_stdin=password_stdin, json_output=json_output)
    if not Security.login(ETHKeyFileSecretManger(password)):
        fail("invalid password", ExitCode.CONFIG_ERROR, json_output=json_output)

    if not json_output:
        typer.echo("\nTesting connections, please wait...")
    timeout = float(ccm.commands_timeout.other_commands_timeout)
    try:
        err_msgs = asyncio.run(asyncio.wait_for(
            UserBalances.instance().update_exchanges(ccm, reconnect=True, exchanges=keyed), timeout))
    except asyncio.TimeoutError:
        fail("network timeout testing connections", ExitCode.TIMEOUT, json_output=json_output)

    rows, data = [], []
    for ex in keyed:
        err = err_msgs.get(ex)
        confirmed = err is None
        rows.append({"exchange": ex, "keys_added": True, "keys_confirmed": confirmed, "error": err})
        data.append([ex, "Yes", "Yes" if confirmed else "No"])

    if json_output:
        print_json({"ok": True, "connections": rows})
        return
    df = pd.DataFrame(data=data, columns=["Exchange", "  Keys Added", "  Keys Confirmed"])
    lines = ["    " + line for line in format_df_for_printout(df, ccm.tables_format).split("\n")]
    typer.echo("\n".join(lines))


def _collect_values(fields: List[Any], cfg: "ClientConfigAdapter",
                    keys_stdin: bool, json_output: bool) -> Dict[str, str]:
    if keys_stdin or not sys.stdin.isatty():
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            fail(f"invalid JSON on stdin: {e}", ExitCode.CONFIG_ERROR, json_output=json_output)
        if not isinstance(payload, dict):
            fail("stdin must be a JSON object of field -> value", ExitCode.CONFIG_ERROR, json_output=json_output)
        values, missing = {}, []
        for f in fields:
            if f.attr in payload:
                values[f.attr] = str(payload[f.attr])
            else:
                missing.append(f.attr)
        if missing:
            fail(f"missing required fields on stdin: {', '.join(missing)}",
                 ExitCode.CONFIG_ERROR, json_output=json_output)
        return values

    values = {}
    for f in fields:
        text = _prompt_text(f, cfg)
        values[f.attr] = (getpass.getpass(f"{text}: ") if f.client_field_data.is_secure
                          else input(f"{text}: "))
    return values


def connect(
    exchange: Optional[str] = typer.Argument(None, help="Exchange to add keys for. Omit to show connections."),
    keys_stdin: bool = typer.Option(False, "--keys-stdin", help="Read API keys as a JSON object from stdin."),
    replace: bool = typer.Option(False, "--replace", help="Overwrite existing keys for the exchange."),
    show_fields: bool = typer.Option(False, "--fields", help="List the exchange's required key fields and exit."),
    show_all: bool = typer.Option(False, "--all", help="List every connectable exchange (no key test)."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Show connections or add an exchange's API keys."""
    from hummingbot.client.config.config_helpers import ClientConfigAdapter, load_client_config_map_from_file
    from hummingbot.client.config.security import Security
    from hummingbot.client.settings import AllConnectorSettings

    if exchange is None:
        if show_all:
            _list_all(json_output)
        else:
            _show_connections(load_client_config_map_from_file(), json_output, password_stdin)
        return

    if exchange not in _connectable_exchanges():
        fail(f"unknown exchange '{exchange}' (run `hbot connect` to list)",
             ExitCode.CONFIG_ERROR, json_output=json_output)

    config_keys = AllConnectorSettings.get_connector_config_keys(exchange)
    if config_keys is None:
        fail(f"'{exchange}' does not use API keys", ExitCode.CONFIG_ERROR, json_output=json_output)
    cfg = ClientConfigAdapter(config_keys)
    fields = _connect_key_fields(cfg)

    if show_fields:
        described = [{"field": f.attr, "prompt": _prompt_text(f, cfg),
                      "secret": bool(f.client_field_data.is_secure)} for f in fields]
        if json_output:
            print_json({"ok": True, "exchange": exchange, "fields": described})
        else:
            typer.echo(f"Required fields for {exchange}:")
            for d in described:
                typer.echo(f"  {d['field']}{' (secret)' if d['secret'] else ''} — {d['prompt']}")
        return

    if Security.connector_config_file_exists(exchange) and not replace:
        fail(f"keys for '{exchange}' already exist; pass --replace to overwrite",
             ExitCode.CONFIG_ERROR, json_output=json_output)

    values = _collect_values(fields, cfg, keys_stdin, json_output)

    login(password_stdin=False, json_output=json_output)

    for attr, value in values.items():
        try:
            setattr(cfg, attr, value)
        except Exception as e:
            fail(f"invalid value for {attr}: {e}", ExitCode.CONFIG_ERROR, json_output=json_output)
    Security.update_secure_config(cfg)

    if json_output:
        print_json({"ok": True, "exchange": exchange, "fields_set": list(values.keys())})
    else:
        typer.echo(f"Stored encrypted keys for {exchange}.")
