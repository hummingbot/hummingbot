"""``hbot history`` — performance/PnL per market & pair, computed from recorded fills."""
import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional

import typer

from hummingbot.cli import bot
from hummingbot.cli.output import print_json

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
            results.append({"market": market, "trading_pair": symbol,
                            "num_trades": len(trades), "error": str(e), "perf": None})
            continue
        results.append({
            "market": market,
            "trading_pair": symbol,
            "num_trades": perf.num_trades,
            "num_buys": perf.num_buys,
            "num_sells": perf.num_sells,
            "base_volume": float(perf.tot_vol_base),
            "quote_volume": float(perf.tot_vol_quote),
            "trade_pnl": float(perf.trade_pnl),
            "fees": float(perf.fee_in_quote),
            "total_pnl": float(perf.total_pnl),
            "return_pct": float(perf.return_pct * 100),
            "balances_available": bool(cur_balances),
            "perf": perf,  # kept for human rendering; stripped before JSON
        })
    return results


def _render_market(market: str, trading_pair: str, perf) -> str:
    """Per-market Trades/Assets/Performance tables — shared with the interactive `history` command."""
    from hummingbot.client.performance import format_performance_by_market
    return "\n".join(format_performance_by_market(market, trading_pair, perf))


def history(
    name: Optional[str] = typer.Argument(None, help="Bot name to view (a past/stopped bot). Omit for the current bot."),
    days: Optional[float] = typer.Option(None, "--days", help="Only include the last N days."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Show profit, fees, and volume per market."""
    from hummingbot.cli.commands._common import resolve_db_for_command
    from hummingbot.cli.data import get_trades
    db_path, config_filter, running = resolve_db_for_command(name, json_output)
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
        if json_output:
            print_json({"ok": True, "markets": []})
        else:
            typer.echo("No trades found.")
        return

    markets = asyncio.run(_compute(fills, balances))

    if json_output:
        clean = [{k: v for k, v in m.items() if k != "perf"} for m in markets]
        print_json({"ok": True, "markets": clean})
        return

    returns = []
    for m in markets:
        if m.get("error") or m.get("perf") is None:
            typer.echo(f"\n{m['market']} / {m['trading_pair']}")
            typer.echo(f"  ({m['num_trades']} trades) error: {m.get('error')}")
            continue
        typer.echo(_render_market(m["market"], m["trading_pair"], m["perf"]))
        if not m["balances_available"]:
            hint = "run `hbot status` to refresh" if running else "bot stopped"
            typer.echo(f"  (current balances unavailable ({hint}) — realized PnL is exact; "
                       f"current/unrealized values approximate)")
        returns.append(m["return_pct"])
    if len(returns) > 1:
        typer.echo(f"\nAveraged Return = {sum(returns) / len(returns):.2f}%")
