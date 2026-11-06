"""``hbot balance`` — fetch balances from connectors connected via `hbot connect`.

Typically run right after `hbot connect <connector>` to confirm the keys work and see funds.
Decrypts the stored keys with the keystore password, queries each connector (network), and reports
balances per connector with their global-token (USD) value, mirroring Hummingbot's ``balance`` command.
Read-only — it never places orders.
"""
import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import typer

from hummingbot.cli.output import ExitCode, echo, emit, fail, json_option, render_table
from hummingbot.cli.password import login


async def _all_prices() -> Tuple[Dict[str, Decimal], str]:
    """Fetch the rate-oracle price list ONCE (not per token, which `get_rate` would do)."""
    from hummingbot.core.rate_oracle.rate_oracle import RateOracle
    ro = RateOracle.get_instance()
    prices = await ro._source.get_prices(quote_token=ro.quote_token)
    return prices, ro.quote_token


def _exchange_assets(connector: str, total: Dict[str, Decimal], available: Dict[str, Decimal],
                     prices: Dict[str, Decimal], quote_token: str) -> Tuple[List[dict], Decimal, Decimal]:
    """Build per-asset rows (with global-token value + allocated %) for one connector.

    Mirrors ``HummingbotApplication.exchange_balances_extra_df``: CEX hides zero balances, gateway
    connectors show them; values come from the pre-fetched rate-oracle prices via ``find_rate``.
    """
    from hummingbot.client.settings import AllConnectorSettings
    from hummingbot.connector.utils import combine_to_hb_trading_pair
    from hummingbot.core.rate_oracle.utils import find_rate
    conn = AllConnectorSettings.get_connector_settings().get(connector)
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


async def _attach_positions(ub, result: Dict[str, dict], timeout: float) -> None:
    """For perpetual connectors, attach open positions + total unrealized PnL, reusing the connectors
    UserBalances already built for the balance fetch (no extra connection)."""
    from hummingbot.cli.commands._common import position_dict as _position_dict
    for ex in result:
        market = getattr(ub, "_markets", {}).get(ex)
        if market is None or not hasattr(market, "account_positions"):
            continue
        try:
            await asyncio.wait_for(market._update_positions(), timeout)
        except Exception:
            continue
        rows = [_position_dict(p) for p in market.account_positions.values() if float(p.amount) != 0]
        result[ex]["positions"] = rows
        result[ex]["pnl_total"] = sum((Decimal(str(r["unrealized_pnl"])) for r in rows), Decimal("0"))


async def _fetch_all(ccm, timeout: float, with_prices: bool = True) -> Dict[str, dict]:
    from hummingbot.user.user_balances import UserBalances
    ub = UserBalances.instance()
    all_total = await asyncio.wait_for(ub.all_balances_all_exchanges(ccm), timeout)
    all_avai = ub.all_available_balances_all_exchanges()
    # --units-only skips the rate-oracle price fetch (the slowest part) and positions.
    prices, quote = (await _all_prices()) if with_prices else ({}, "")
    result = {ex: dict(zip(("assets", "allocated_total", "usd_total"),
                           _exchange_assets(ex, total, all_avai.get(ex, {}), prices, quote)))
              for ex, total in all_total.items()}
    if with_prices:
        await _attach_positions(ub, result, timeout)
    return result


async def _fetch_one(ccm, connector: str, timeout: float,
                     with_prices: bool = True) -> Tuple[Optional[Dict[str, dict]], Optional[str]]:
    from hummingbot.user.user_balances import UserBalances
    ub = UserBalances.instance()
    err = await asyncio.wait_for(ub.update_exchange_balance(connector, ccm), timeout)
    if err is not None:
        return None, err
    total = ub.all_balances(connector)
    avai = ub.all_available_balances_all_exchanges().get(connector, {})
    prices, quote = (await _all_prices()) if with_prices else ({}, "")
    assets, alloc, usd = _exchange_assets(connector, total, avai, prices, quote)
    result = {connector: {"assets": assets, "allocated_total": alloc, "usd_total": usd}}
    if with_prices:
        await _attach_positions(ub, result, timeout)
    return result, None


def _render(result: Dict[str, dict], sym: str, units_only: bool = False) -> str:
    """Render balances (+ positions on perps) as per-connector Markdown, with a net-value total.

    ``units_only`` hides the USD value column and all value totals (no prices were fetched).
    """
    from hummingbot.client.performance import PerformanceMetrics
    rnd = PerformanceMetrics.smart_round
    out: List[str] = []
    exchanges_total = Decimal("0")
    for ex, data in result.items():
        positions = data.get("positions") or []
        pnl = data.get("pnl_total", Decimal("0"))
        usd = data["usd_total"]
        net = usd + pnl                       # net value = balances value + unrealized PnL
        assets = data["assets"]
        if not assets and not positions:
            out.append(f"## {ex}\n\n_(no balance)_")
            continue
        section = f"## {ex}\n\n"
        if assets:
            if units_only:
                rows = [{"asset": a["asset"], "total": float(a["total"]),
                         "available": float(a["available"])} for a in assets]
                section += render_table(rows)
            else:
                rows = [{"asset": a["asset"], "total": float(a["total"]),
                         f"value({sym})": float(a["value"]), "allocated": a["allocated"]} for a in assets]
                pct = (data["allocated_total"] / usd) if usd != Decimal("0") else 0
                section += render_table(rows) + f"\n\nbalances: {sym}{rnd(usd)} | allocated: {pct:.2%}"
        if positions:
            pos_rows = [{"pair": p["trading_pair"], "side": p["side"], "amount": p["amount"],
                         "entry": p["entry_price"], "notional": p["notional"],
                         "uPnL": p["unrealized_pnl"], "lev": p["leverage"]} for p in positions]
            section += "\n\npositions:\n" + render_table(pos_rows)
            section += (f"\n\nnet value: {sym}{rnd(net)}  "
                        f"(balances {sym}{rnd(usd)} + uPnL {sym}{rnd(pnl)})")
        out.append(section)
        exchanges_total += net
    if units_only:
        return "\n\n".join(out)
    out.append(f"connectors total (net): {sym}{exchanges_total:.2f}")
    return "\n\n".join(out)


def _json_payload(result: Dict[str, dict], quote: str, units_only: bool) -> dict:
    """The --json shape: raw numbers per connector (no Markdown, no rendering-only fields)."""
    payload: dict = {"quote": None if units_only else quote, "connectors": {}}
    total = Decimal("0")
    for ex, data in result.items():
        entry: dict = {"assets": [
            {"asset": a["asset"], "total": float(a["total"]), "available": float(a["available"]),
             **({} if units_only else {"value": float(a["value"])})} for a in data["assets"]]}
        if not units_only:
            entry["balances_value"] = float(data["usd_total"])
            entry["allocated_value"] = float(data["allocated_total"])
            pnl = data.get("pnl_total", Decimal("0"))
            if "positions" in data:
                entry["positions"] = data["positions"]
                entry["unrealized_pnl"] = float(pnl)
            entry["net_value"] = float(data["usd_total"] + pnl)
            total += data["usd_total"] + pnl
        payload["connectors"][ex] = entry
    if not units_only:
        payload["net_value_total"] = float(total)
    return payload


def balance(
    connector: Optional[str] = typer.Argument(None, help="Connector to fetch. Omit for all connected connectors."),
    units_only: bool = typer.Option(
        False, "--units-only", help="Show only token amounts — skip the price fetch (faster) and USD values/positions."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
    as_json: bool = json_option(),
) -> None:
    """Show your connector balances, with their value in USD."""
    from hummingbot.client.settings import AllConnectorSettings
    ccm, password = login(password_stdin=password_stdin)

    sym = ccm.global_token.global_token_symbol
    timeout = float(ccm.commands_timeout.other_commands_timeout)
    typer.echo("Updating balances, please wait...", err=True)
    with_prices = not units_only

    if connector is not None:
        if connector not in AllConnectorSettings.get_connector_settings():
            fail(f"unknown connector '{connector}'", ExitCode.CONFIG_ERROR)
        try:
            result, err = asyncio.run(_fetch_one(ccm, connector, timeout, with_prices))
        except asyncio.TimeoutError:
            fail("network timeout fetching balances", ExitCode.TIMEOUT)
        if err is not None:
            fail(f"{connector}: {err}", ExitCode.ERROR)
    else:
        try:
            result = asyncio.run(_fetch_all(ccm, timeout, with_prices))
        except asyncio.TimeoutError:
            fail("network timeout fetching balances", ExitCode.TIMEOUT)

    if as_json:
        emit(_json_payload(result, quote=sym, units_only=units_only), "", True)
    elif not result:
        echo("No balances (no connected connectors, or all balances are zero).")
    else:
        echo(_render(result, sym, units_only))
