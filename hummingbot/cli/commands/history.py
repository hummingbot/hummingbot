"""``hbot history`` — performance/PnL per market & pair, computed from recorded fills."""
import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional

import typer

from hummingbot.cli import bot
from hummingbot.cli.output import echo, render_table

PERF_TIMEOUT = 30.0


def _balances_for_market(market: str, balances: Dict[str, Dict[str, float]]) -> Dict[str, Decimal]:
    src = balances.get(market)
    if not src:
        # Fall back to a merged view across connectors if we can't match exactly.
        merged: Dict[str, float] = defaultdict(float)
        for per_connector in balances.values():
            for asset, amt in per_connector.items():
                merged[asset] += amt
        src = dict(merged)
    return {asset: Decimal(str(amt)) for asset, amt in src.items()}


async def _compute(fills: list, balances: Dict[str, Dict[str, float]]) -> List[dict]:
    from hummingbot.client.performance import PerformanceMetrics

    groups: Dict[tuple, list] = defaultdict(list)
    for t in fills:
        groups[(t.market, t.symbol)].append(t)

    results: List[dict] = []
    for (market, symbol), trades in groups.items():
        cur_balances = _balances_for_market(market, balances)
        try:
            perf = await asyncio.wait_for(
                PerformanceMetrics.create(symbol, trades, cur_balances), PERF_TIMEOUT)
        except Exception as e:
            results.append({"market": market, "pair": symbol, "trades": len(trades),
                            "error": str(e)})
            continue
        results.append({
            "market": market,
            "pair": symbol,
            "trades": perf.num_trades,
            "buys": perf.num_buys,
            "sells": perf.num_sells,
            "base_vol": float(perf.tot_vol_base),
            "quote_vol": float(perf.tot_vol_quote),
            "trade_pnl": float(perf.trade_pnl),
            "fees": float(perf.fee_in_quote),
            "total_pnl": float(perf.total_pnl),
            "return%": round(float(perf.return_pct * 100), 4),
            "balances_available": bool(cur_balances),
        })
    return results


def history(
    name: Optional[str] = typer.Argument(None, help="Bot name to view (a past/stopped bot). Omit for the current bot."),
    days: Optional[float] = typer.Option(None, "--days", help="Only include the last N days."),
) -> None:
    """Show profit, fees, and volume per market."""
    from hummingbot.cli.commands._common import resolve_db_for_command
    from hummingbot.cli.data import get_trades
    db_path, config_filter, running = resolve_db_for_command(name)
    balances: dict = {}
    if name is None:
        # Fills/PnL come from sqlite (exact, fast). For current balances we REUSE the engine's last
        # snapshot (written on every `hbot status`) — no live fetch, so history stays fast when you're
        # already polling status. Only if the bot is running and we have no cached balances do we ask
        # for one fresh snapshot to bootstrap them.
        balances = (bot.read_status() or {}).get("balances") or {}
        if running and not balances:
            from hummingbot.cli.commands.status import _request_fresh_snapshot
            _request_fresh_snapshot()
            balances = (bot.read_status() or {}).get("balances") or {}

    fills = get_trades(db_path, config_file_path=config_filter, days=days)
    if not fills:
        echo("No trades found.")
        return

    markets = asyncio.run(_compute(fills, balances))

    cols = ["market", "pair", "trades", "buys", "sells", "base_vol", "quote_vol",
            "trade_pnl", "fees", "total_pnl", "return%"]
    echo(render_table(markets, columns=cols, title=f"history {name}" if name else "history"))

    ok = [m for m in markets if "error" not in m]
    returns = [m["return%"] for m in ok]
    if len(returns) > 1:
        echo(f"\naveraged return: {sum(returns) / len(returns):.2f}%")
    if any(not m["balances_available"] for m in ok):
        hint = "run `hbot status` to refresh" if running else "bot stopped"
        echo(f"\n(current balances unavailable for some markets ({hint}) — realized PnL is exact; "
             f"current/unrealized values approximate)")
    for m in markets:
        if "error" in m:
            echo(f"\n{m['market']}/{m['pair']}: ({m['trades']} trades) error: {m['error']}")
