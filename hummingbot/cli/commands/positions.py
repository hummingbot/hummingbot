"""``hbot positions`` — open positions on a perpetual exchange.

Private (account) data, so it unlocks the keystore and uses your stored keys — unlike the public
market-data commands. Reports each open position's side, size, entry price, notional, unrealized PnL,
and leverage.
"""
import asyncio
from typing import List, Optional, Tuple

import typer

from hummingbot.cli.output import ExitCode, echo, fail, render_table
from hummingbot.cli.password import login


def _position_dict(p) -> dict:
    amt = float(p.amount)
    entry = float(p.entry_price)
    upnl = float(p.unrealized_pnl)
    # Current mark is exact from the position's own data (uPnL = amount*(mark-entry) for linear
    # perps), so the market value needs no rate-oracle / price fetch.
    mark = entry + (upnl / amt) if amt else entry
    return {
        "trading_pair": p.trading_pair,
        "side": getattr(p.position_side, "name", str(p.position_side)),
        "amount": amt,
        "entry_price": entry,
        "mark_price": mark,
        "value": abs(amt) * mark,          # current market value (notional at mark, in quote currency)
        "notional": abs(amt) * entry,      # entry notional (kept for balance's existing render)
        "unrealized_pnl": upnl,
        "leverage": int(p.leverage),
    }


async def _fetch(ccm, exchange: str, timeout: float) -> Tuple[Optional[List[dict]], Optional[str]]:
    from hummingbot.client.config.security import Security
    from hummingbot.user.user_balances import UserBalances
    keys = Security.api_keys(exchange)
    if not keys:
        return None, f"no keys for '{exchange}' — run `hbot connect {exchange}` first"
    market = UserBalances.connect_market(exchange, ccm, **keys)
    if market is None or not hasattr(market, "account_positions"):
        return None, f"'{exchange}' is not a perpetual exchange (no positions)"
    await asyncio.wait_for(market._update_positions(), timeout)
    rows = [_position_dict(p) for p in market.account_positions.values() if float(p.amount) != 0]
    return rows, None


def positions(
    exchange: str = typer.Argument(..., help="Perpetual exchange, e.g. hyperliquid_perpetual."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
) -> None:
    """Show your open positions on a perpetual exchange."""
    ccm, _ = login(password_stdin=password_stdin)
    timeout = float(ccm.commands_timeout.other_commands_timeout)
    typer.echo("Fetching positions, please wait...", err=True)
    try:
        rows, err = asyncio.run(_fetch(ccm, exchange, timeout))
    except asyncio.TimeoutError:
        fail("network timeout fetching positions", ExitCode.TIMEOUT)
    if err is not None:
        fail(err, ExitCode.CONFIG_ERROR)

    if not rows:
        echo(f"## positions {exchange}\n\n_(no open positions)_")
    else:
        echo(render_table(rows, title=f"positions {exchange}",
                          columns=["trading_pair", "side", "amount", "entry_price",
                                   "mark_price", "value", "unrealized_pnl", "leverage"]))
