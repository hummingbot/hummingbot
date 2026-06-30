"""``hbot connect`` — list connectors and securely store encrypted API keys.

Like Hummingbot's ``connect``: each connector declares its own key fields (api key, secret, etc.).
Secrets are NEVER taken as flags. Supply them either interactively (hidden prompts) or, for
automation, as a JSON object on stdin (``--keys-stdin``). Keys are encrypted with the keystore
password via ``Security.update_secure_config`` and written to ``conf/connectors/<connector>.yml``.
"""
import asyncio
import getpass
import sys
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import typer

from hummingbot.cli.output import ExitCode, echo, fail, render_kv, render_table
from hummingbot.cli.password import login, resolve_password

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


def _connectable_exchanges() -> List[str]:
    from hummingbot.client.settings import connectable_exchange_names
    return sorted(connectable_exchange_names())


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


def _list_all() -> None:
    """Static checklist of every connectable connector (no password / network needed)."""
    from hummingbot.client.config.security import Security
    rows = [{"connector": name, "keys_added": Security.connector_config_file_exists(name)}
            for name in _connectable_exchanges()]
    echo(render_table(rows, columns=["connector", "keys_added"], title="connectable connectors"))


def _show_connections(ccm, password_stdin: bool) -> None:
    """Hummingbot-style ``connect`` table: tests the keys you've added and reports Keys Confirmed."""
    from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
    from hummingbot.client.config.security import Security
    from hummingbot.user.user_balances import UserBalances
    keyed = [name for name in _connectable_exchanges() if Security.connector_config_file_exists(name)]
    if not keyed:
        echo("No connectors connected. Run `hbot connect <connector>` to add keys, "
             "or `hbot connect --all` to list connectable connectors.")
        return

    password = resolve_password(password_stdin=password_stdin)
    if not Security.login(ETHKeyFileSecretManger(password)):
        fail("invalid password", ExitCode.CONFIG_ERROR)

    typer.echo("Testing connections, please wait...", err=True)
    timeout = float(ccm.commands_timeout.other_commands_timeout)
    try:
        err_msgs = asyncio.run(asyncio.wait_for(
            UserBalances.instance().update_exchanges(ccm, reconnect=True, exchanges=keyed), timeout))
    except asyncio.TimeoutError:
        fail("network timeout testing connections", ExitCode.TIMEOUT)

    rows = []
    for ex in keyed:
        err = err_msgs.get(ex)
        rows.append({"connector": ex, "keys_added": True, "keys_confirmed": err is None, "error": err})
    echo(render_table(rows, columns=["connector", "keys_added", "keys_confirmed", "error"],
                      title="connections"))


def _collect_key_values(fields: List[Any], cfg: "ClientConfigAdapter",
                        keys_stdin: bool) -> Dict[str, str]:
    if keys_stdin or not sys.stdin.isatty():
        from hummingbot.cli.commands._common import read_json_object_from_stdin
        payload = read_json_object_from_stdin()
        values, missing = {}, []
        for f in fields:
            if f.attr in payload:
                values[f.attr] = str(payload[f.attr])
            else:
                missing.append(f.attr)
        if missing:
            fail(f"missing required fields on stdin: {', '.join(missing)}",
                 ExitCode.CONFIG_ERROR)
        return values

    values = {}
    for f in fields:
        text = _prompt_text(f, cfg)
        values[f.attr] = (getpass.getpass(f"{text}: ") if f.client_field_data.is_secure
                          else input(f"{text}: "))
    return values


def connect(
    connector: Optional[str] = typer.Argument(None, help="Connector to add keys for. Omit to show connections."),
    keys_stdin: bool = typer.Option(False, "--keys-stdin", help="Read API keys as a JSON object from stdin."),
    replace: bool = typer.Option(False, "--replace", help="Overwrite existing keys for the connector."),
    show_fields: bool = typer.Option(False, "--fields", help="List the connector's required key fields and exit."),
    show_all: bool = typer.Option(False, "--all", help="List every connectable connector (no key test)."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
) -> None:
    """Show connections or add a connector's API keys."""
    from hummingbot.client.config.config_helpers import ClientConfigAdapter, load_client_config_map_from_file
    from hummingbot.client.config.security import Security
    from hummingbot.client.settings import AllConnectorSettings

    if connector is None:
        if show_all:
            _list_all()
        else:
            _show_connections(load_client_config_map_from_file(), password_stdin)
        return

    if connector not in _connectable_exchanges():
        fail(f"unknown connector '{connector}' (run `hbot connect` to list)",
             ExitCode.CONFIG_ERROR)

    config_keys = AllConnectorSettings.get_connector_config_keys(connector)
    if config_keys is None:
        fail(f"'{connector}' does not use API keys", ExitCode.CONFIG_ERROR)
    cfg = ClientConfigAdapter(config_keys)
    fields = _connect_key_fields(cfg)

    if show_fields:
        described = [{"field": f.attr, "prompt": _prompt_text(f, cfg),
                      "secret": bool(f.client_field_data.is_secure)} for f in fields]
        echo(render_table(described, columns=["field", "secret", "prompt"],
                          title=f"key fields for {connector}"))
        return

    if Security.connector_config_file_exists(connector) and not replace:
        fail(f"keys for '{connector}' already exist; pass --replace to overwrite",
             ExitCode.CONFIG_ERROR)

    values = _collect_key_values(fields, cfg, keys_stdin)

    login(password_stdin=False)

    for attr, value in values.items():
        try:
            setattr(cfg, attr, value)
        except Exception as e:
            fail(f"invalid value for {attr}: {e}", ExitCode.CONFIG_ERROR)
    Security.update_secure_config(cfg)

    echo(render_kv({"connector": connector, "fields_set": ", ".join(values.keys())}, title="connect"))
