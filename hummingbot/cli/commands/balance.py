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

from hummingbot.cli.output import ExitCode, echo, fail, render_table
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


async def _attach_positions(ub, result: Dict[str, dict], timeout: float) -> None:
    """For perpetual exchanges, attach open positions + total unrealized PnL, reusing the connectors
    UserBalances already built for the balance fetch (no extra connection)."""
    from hummingbot.cli.commands.positions import _position_dict
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


async def _fetch_all(ccm, timeout: float) -> Dict[str, dict]:
    from hummingbot.user.user_balances import UserBalances
    ub = UserBalances.instance()
    all_total = await asyncio.wait_for(ub.all_balances_all_exchanges(ccm), timeout)
    all_avai = ub.all_available_balances_all_exchanges()
    prices, quote = await _all_prices()
    result = {ex: dict(zip(("assets", "allocated_total", "usd_total"),
                           _exchange_assets(ex, total, all_avai.get(ex, {}), prices, quote)))
              for ex, total in all_total.items()}
    await _attach_positions(ub, result, timeout)
    return result


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
    result = {exchange: {"assets": assets, "allocated_total": alloc, "usd_total": usd}}
    await _attach_positions(ub, result, timeout)
    return result, None


def _render(result: Dict[str, dict], sym: str) -> str:
    """Render balances (+ positions on perps) as per-exchange Markdown, with a net-value total."""
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
    out.append(f"exchanges total (net): {sym}{exchanges_total:.2f}")
    return "\n\n".join(out)


def balance(
    exchange: Optional[str] = typer.Argument(None, help="Exchange to fetch. Omit for all connected exchanges."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
) -> None:
    """Show your exchange balances, with their value in USD."""
    from hummingbot.client.settings import AllConnectorSettings
    ccm, password = login(password_stdin=password_stdin)

    sym = ccm.global_token.global_token_symbol
    timeout = float(ccm.commands_timeout.other_commands_timeout)
    typer.echo("Updating balances, please wait...", err=True)

    if exchange is not None:
        if exchange not in AllConnectorSettings.get_connector_settings():
            fail(f"unknown exchange '{exchange}'", ExitCode.CONFIG_ERROR)
        try:
            result, err = asyncio.run(_fetch_one(ccm, exchange, timeout))
        except asyncio.TimeoutError:
            fail("network timeout fetching balances", ExitCode.TIMEOUT)
        if err is not None:
            fail(f"{exchange}: {err}", ExitCode.ERROR)
    else:
        try:
            result = asyncio.run(_fetch_all(ccm, timeout))
        except asyncio.TimeoutError:
            fail("network timeout fetching balances", ExitCode.TIMEOUT)

    if not result:
        echo("No balances (no connected exchanges, or all balances are zero).")
    else:
        echo(_render(result, sym))
