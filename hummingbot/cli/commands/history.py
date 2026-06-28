"""``hbot history`` — performance/PnL per market & pair, computed from recorded fills."""
import asyncio
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import typer

from hummingbot import data_path
from hummingbot.cli.data import get_trades
from hummingbot.cli.instances import Instance
from hummingbot.cli.output import ExitCode, fail, print_json

PERF_TIMEOUT = 30.0


def _resolve_db_path(instance: Instance) -> Optional[str]:
    db_path = instance.db_path()
    if db_path and Path(db_path).exists():
        return db_path
    fallback = Path(data_path()) / f"{instance.name}.sqlite"
    return str(fallback) if fallback.exists() else None


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
                            "num_trades": len(trades), "error": str(e)})
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
        })
    return results


def history(
    name: str = typer.Argument(..., help="Instance id."),
    days: Optional[float] = typer.Option(None, "--days", help="Only include the last N days."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Report PnL, fees, and volume per market/pair from the bot's trade history."""
    instance = Instance(name)
    if not instance.exists():
        fail(f"instance '{name}' not found", ExitCode.NOT_FOUND, json_output=json_output)

    db_path = _resolve_db_path(instance)
    if db_path is None:
        fail(f"no trades database found for '{name}' (no fills yet?)",
             ExitCode.ERROR, json_output=json_output)

    fills = get_trades(db_path, config_file_path=instance.config_file_path(), days=days)
    if not fills:
        if json_output:
            print_json({"ok": True, "name": name, "markets": []})
        else:
            typer.echo("No trades found.")
        return

    balances = (instance.read_status() or {}).get("balances") or {}
    markets = asyncio.run(_compute(fills, balances))

    if json_output:
        print_json({"ok": True, "name": name, "markets": markets})
        return

    for m in markets:
        typer.echo(f"\n{m['market']} / {m['trading_pair']}")
        if "error" in m:
            typer.echo(f"  ({m['num_trades']} trades) error: {m['error']}")
            continue
        typer.echo(f"  trades: {m['num_trades']} ({m['num_buys']} buys / {m['num_sells']} sells)")
        typer.echo(f"  volume: {m['base_volume']:.6g} base / {m['quote_volume']:.6g} quote")
        typer.echo(f"  trade PnL: {m['trade_pnl']:.6g}   fees: {m['fees']:.6g}")
        typer.echo(f"  total PnL: {m['total_pnl']:.6g}   return: {m['return_pct']:.4g}%"
                   + ("" if m["balances_available"] else "  (balances unavailable — bot stopped)"))
