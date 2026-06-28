"""``hbot balance`` — fetch balances from exchanges connected via `hbot connect`.

Typically run right after `hbot connect <exchange>` to confirm the keys work and see funds.
Decrypts the stored keys with the keystore password, queries each exchange (network), and reports
non-zero total/available balances. Read-only — it never places orders.
"""
import asyncio
from decimal import Decimal
from typing import Dict, Optional, Tuple

import typer

from hummingbot.cli.output import ExitCode, fail, print_json
from hummingbot.cli.password import resolve_password
from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.config_helpers import load_client_config_map_from_file
from hummingbot.client.config.security import Security
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.user.user_balances import UserBalances


def _nonzero(total: Dict[str, Decimal], available: Dict[str, Decimal]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for asset, amount in total.items():
        if amount and Decimal(str(amount)) != 0:
            out[asset] = {"total": float(amount), "available": float(available.get(asset, 0) or 0)}
    return out


async def _fetch_all(ccm, timeout: float) -> Dict[str, Dict[str, Dict[str, float]]]:
    ub = UserBalances.instance()
    all_total = await asyncio.wait_for(ub.all_balances_all_exchanges(ccm), timeout)
    all_available = ub.all_available_balances_all_exchanges()
    return {ex: _nonzero(bals, all_available.get(ex, {})) for ex, bals in all_total.items()}


async def _fetch_one(ccm, exchange: str, timeout: float) -> Tuple[Optional[Dict[str, Dict[str, float]]], Optional[str]]:
    ub = UserBalances.instance()
    err = await asyncio.wait_for(ub.update_exchange_balance(exchange, ccm), timeout)
    if err is not None:
        return None, err
    total = ub.all_balances(exchange)
    available = ub.all_available_balances_all_exchanges().get(exchange, {})
    return _nonzero(total, available), None


def _print_human(result: Dict[str, Dict[str, Dict[str, float]]]) -> None:
    if not result:
        typer.echo("No balances (no connected exchanges, or all balances are zero).")
        return
    for ex, assets in result.items():
        typer.echo(f"\n{ex}:")
        if not assets:
            typer.echo("  (no balance)")
            continue
        for asset, amt in sorted(assets.items()):
            typer.echo(f"  {asset:<8} {amt['total']:>18.8f}  (available {amt['available']:.8f})")


def balance(
    exchange: Optional[str] = typer.Argument(None, help="Exchange to fetch. Omit for all connected exchanges."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Fetch balances from exchanges you've connected with `hbot connect`."""
    password = resolve_password(password_stdin=password_stdin, json_output=json_output)
    ccm = load_client_config_map_from_file()
    if not Security.login(ETHKeyFileSecretManger(password)):
        fail("invalid password", ExitCode.CONFIG_ERROR, json_output=json_output)

    timeout = float(ccm.commands_timeout.other_commands_timeout)

    if exchange is not None:
        if exchange not in AllConnectorSettings.get_connector_settings():
            fail(f"unknown exchange '{exchange}'", ExitCode.CONFIG_ERROR, json_output=json_output)
        try:
            balances, err = asyncio.run(_fetch_one(ccm, exchange, timeout))
        except asyncio.TimeoutError:
            fail("network timeout fetching balances", ExitCode.TIMEOUT, json_output=json_output)
        if err is not None:
            fail(f"{exchange}: {err}", ExitCode.ERROR, json_output=json_output)
        result = {exchange: balances}
    else:
        try:
            result = asyncio.run(_fetch_all(ccm, timeout))
        except asyncio.TimeoutError:
            fail("network timeout fetching balances", ExitCode.TIMEOUT, json_output=json_output)

    if json_output:
        print_json({"ok": True, "balances": result})
    else:
        _print_human(result)
