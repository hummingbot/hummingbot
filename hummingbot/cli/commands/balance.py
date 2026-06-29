"""``hbot balance`` — fetch balances from exchanges connected via `hbot connect`.

Typically run right after `hbot connect <exchange>` to confirm the keys work and see funds.
Decrypts the stored keys with the keystore password, queries each exchange (network), and reports
balances per exchange with their global-token (USD) value, mirroring Hummingbot's ``balance`` command.
Read-only — it never places orders.
"""
import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import typer

from hummingbot.cli.output import ExitCode, fail, print_json
from hummingbot.cli.password import login


async def _all_prices() -> Tuple[Dict[str, Decimal], str]:
    """Fetch the rate-oracle price list ONCE (not per token, which `get_rate` would do)."""
    from hummingbot.core.rate_oracle.rate_oracle import RateOracle
    ro = RateOracle.get_instance()
    prices = await ro._source.get_prices(quote_token=ro.quote_token)
    return prices, ro.quote_token


def _exchange_assets(exchange: str, total: Dict[str, Decimal], available: Dict[str, Decimal],
                     prices: Dict[str, Decimal], quote_token: str) -> Tuple[List[dict], Decimal, Decimal]:
    """Build per-asset rows (with global-token value + allocated %) for one exchange.

    Mirrors ``HummingbotApplication.exchange_balances_extra_df``: CEX hides zero balances, gateway
    connectors show them; values come from the pre-fetched rate-oracle prices via ``find_rate``.
    """
    from hummingbot.client.settings import AllConnectorSettings
    from hummingbot.connector.utils import combine_to_hb_trading_pair
    from hummingbot.core.rate_oracle.utils import find_rate
    conn = AllConnectorSettings.get_connector_settings().get(exchange)
    is_gateway = bool(conn and conn.uses_gateway_generic_connector())
    assets: List[dict] = []
    allocated_total = Decimal("0")
    usd_total = Decimal("0")
    for token, bal in total.items():
        bal = Decimal(str(bal))
        avai = Decimal(str(available.get(token.upper(), 0) or 0))
        if bal == Decimal(0) and not is_gateway:
            continue
        allocated = "0%" if bal == Decimal(0) else f"{(bal - avai) / bal:.0%}"
        rate = find_rate(prices, combine_to_hb_trading_pair(base=token, quote=quote_token))
        rate = Decimal("0") if rate is None else rate
        value = rate * bal
        allocated_total += rate * (bal - avai)
        usd_total += value
        assets.append({"asset": token.upper(), "total": bal, "available": avai,
                       "value": value, "allocated": allocated})
    assets.sort(key=lambda a: a["asset"])
    return assets, allocated_total, usd_total


async def _fetch_all(ccm, timeout: float) -> Dict[str, dict]:
    from hummingbot.user.user_balances import UserBalances
    ub = UserBalances.instance()
    all_total = await asyncio.wait_for(ub.all_balances_all_exchanges(ccm), timeout)
    all_avai = ub.all_available_balances_all_exchanges()
    prices, quote = await _all_prices()
    return {ex: dict(zip(("assets", "allocated_total", "usd_total"),
                         _exchange_assets(ex, total, all_avai.get(ex, {}), prices, quote)))
            for ex, total in all_total.items()}


async def _fetch_one(ccm, exchange: str, timeout: float) -> Tuple[Optional[Dict[str, dict]], Optional[str]]:
    from hummingbot.user.user_balances import UserBalances
    ub = UserBalances.instance()
    err = await asyncio.wait_for(ub.update_exchange_balance(exchange, ccm), timeout)
    if err is not None:
        return None, err
    total = ub.all_balances(exchange)
    avai = ub.all_available_balances_all_exchanges().get(exchange, {})
    prices, quote = await _all_prices()
    assets, alloc, usd = _exchange_assets(exchange, total, avai, prices, quote)
    return {exchange: {"assets": assets, "allocated_total": alloc, "usd_total": usd}}, None


def _render(result: Dict[str, dict], sym: str) -> str:
    """Render like Hummingbot's ``balance``: per-exchange table + Total/Allocated, then Exchanges Total."""
    import pandas as pd

    from hummingbot.client.performance import PerformanceMetrics
    out: List[str] = []
    exchanges_total = Decimal("0")
    for ex, data in result.items():
        out.append(f"\n{ex}:")
        assets = data["assets"]
        if not assets:
            out.append("You have no balance on this exchange.")
            continue
        df = pd.DataFrame([{
            "Asset": a["asset"],
            "Total": round(a["total"], 4),
            f"Total ({sym})": PerformanceMetrics.smart_round(a["value"]),
            "Allocated": a["allocated"],
        } for a in assets])
        out.append("\n".join("    " + line for line in df.to_string(index=False).split("\n")))
        out.append(f"\n  Total: {sym} {PerformanceMetrics.smart_round(data['usd_total'])}")
        pct = (data["allocated_total"] / data["usd_total"]) if data["usd_total"] != Decimal("0") else 0
        out.append(f"Allocated: {pct:.2%}")
        exchanges_total += data["usd_total"]
    out.append(f"\n\nExchanges Total: {sym} {exchanges_total:.0f}    ")
    return "\n".join(out)


def _to_json(result: Dict[str, dict], sym: str) -> dict:
    exchanges_total = Decimal("0")
    exchanges = {}
    for ex, data in result.items():
        exchanges_total += data["usd_total"]
        pct = float(data["allocated_total"] / data["usd_total"]) if data["usd_total"] != Decimal("0") else 0.0
        exchanges[ex] = {
            "assets": [{"asset": a["asset"], "total": float(a["total"]), "available": float(a["available"]),
                        "value": float(a["value"]), "allocated": a["allocated"]} for a in data["assets"]],
            "total_value": float(data["usd_total"]),
            "allocated_pct": pct,
        }
    return {"ok": True, "global_token": sym, "exchanges": exchanges, "total_value": float(exchanges_total)}


def balance(
    exchange: Optional[str] = typer.Argument(None, help="Exchange to fetch. Omit for all connected exchanges."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Show your exchange balances, with their value in USD."""
    from hummingbot.client.settings import AllConnectorSettings
    ccm, password = login(password_stdin=password_stdin, json_output=json_output)

    sym = ccm.global_token.global_token_symbol
    timeout = float(ccm.commands_timeout.other_commands_timeout)
    if not json_output:
        typer.echo("Updating balances, please wait...")

    if exchange is not None:
        if exchange not in AllConnectorSettings.get_connector_settings():
            fail(f"unknown exchange '{exchange}'", ExitCode.CONFIG_ERROR, json_output=json_output)
        try:
            result, err = asyncio.run(_fetch_one(ccm, exchange, timeout))
        except asyncio.TimeoutError:
            fail("network timeout fetching balances", ExitCode.TIMEOUT, json_output=json_output)
        if err is not None:
            fail(f"{exchange}: {err}", ExitCode.ERROR, json_output=json_output)
    else:
        try:
            result = asyncio.run(_fetch_all(ccm, timeout))
        except asyncio.TimeoutError:
            fail("network timeout fetching balances", ExitCode.TIMEOUT, json_output=json_output)

    if json_output:
        print_json(_to_json(result, sym))
    elif not result:
        typer.echo("No balances (no connected exchanges, or all balances are zero).")
    else:
        typer.echo(_render(result, sym))
