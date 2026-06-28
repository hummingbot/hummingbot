"""``hbot history`` — performance/PnL per market & pair, computed from recorded fills."""
import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional

import typer

from hummingbot.cli import bot
from hummingbot.cli.commands.status import _request_fresh_snapshot
from hummingbot.cli.output import ExitCode, fail, print_json

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
    """Per-market Trades/Assets/Performance tables — mirrors HummingbotApplication.report_performance_by_market."""
    import pandas as pd

    from hummingbot.client.performance import PerformanceMetrics
    from hummingbot.client.settings import AllConnectorSettings

    sr = PerformanceMetrics.smart_round
    is_deriv = market in AllConnectorSettings.get_derivative_names()
    base, quote = trading_pair.split("-")
    lines = [f"\n{market} / {trading_pair}"]

    trades_df = pd.DataFrame(
        data=[[f"{'Number of trades':<27}", perf.num_buys, perf.num_sells, perf.num_trades],
              [f"{f'Total trade volume ({base})':<27}", sr(perf.b_vol_base), sr(perf.s_vol_base), sr(perf.tot_vol_base)],
              [f"{f'Total trade volume ({quote})':<27}", sr(perf.b_vol_quote), sr(perf.s_vol_quote),
               sr(perf.tot_vol_quote)],
              [f"{'Avg price':<27}", sr(perf.avg_b_price), sr(perf.avg_s_price), sr(perf.avg_tot_price)]],
        columns=["", "buy", "sell", "total"])
    lines += ["", "  Trades:"] + ["    " + ln for ln in trades_df.to_string(index=False).split("\n")]

    assets_df = pd.DataFrame(
        data=[[f"{base:<17}", "-", "-", "-"] if is_deriv else
              [f"{base:<17}", sr(perf.start_base_bal), sr(perf.cur_base_bal), sr(perf.tot_vol_base)],
              [f"{quote:<17}", sr(perf.start_quote_bal), sr(perf.cur_quote_bal), sr(perf.tot_vol_quote)],
              [f"{trading_pair + ' price':<17}", sr(perf.start_price), sr(perf.cur_price),
               sr(perf.cur_price - perf.start_price)],
              [f"{'Base asset %':<17}", "-", "-", "-"] if is_deriv else
              [f"{'Base asset %':<17}", f"{perf.start_base_ratio_pct:.2%}", f"{perf.cur_base_ratio_pct:.2%}",
               f"{perf.cur_base_ratio_pct - perf.start_base_ratio_pct:.2%}"]],
        columns=["", "start", "current", "change"])
    lines += ["", "  Assets:"] + ["    " + ln for ln in assets_df.to_string(index=False).split("\n")]

    perf_data = [["Hold portfolio value    ", f"{sr(perf.hold_value)} {quote}"],
                 ["Current portfolio value ", f"{sr(perf.cur_value)} {quote}"],
                 ["Trade P&L               ", f"{sr(perf.trade_pnl)} {quote}"]]
    perf_data += [["Fees paid               ", f"{sr(amt)} {tok}"] for tok, amt in perf.fees.items()]
    perf_data += [["Total P&L               ", f"{sr(perf.total_pnl)} {quote}"],
                  ["Return %                ", f"{perf.return_pct:.2%}"]]
    perf_df = pd.DataFrame(data=perf_data)
    lines += ["", "  Performance:"] + ["    " + ln for ln in perf_df.to_string(index=False, header=False).split("\n")]
    return "\n".join(lines)


def history(
    days: Optional[float] = typer.Option(None, "--days", help="Only include the last N days."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Report PnL, fees, and volume per market/pair from the bot's trade history."""
    from hummingbot.cli.data import get_trades
    if not bot.exists():
        fail("no bot has been started", ExitCode.NOT_FOUND, json_output=json_output)

    db_path = bot.resolve_db_path()
    if db_path is None:
        fail("no trades database yet (no fills?)", ExitCode.ERROR, json_output=json_output)

    fills = get_trades(db_path, config_file_path=bot.config_file_path(), days=days)
    if not fills:
        if json_output:
            print_json({"ok": True, "markets": []})
        else:
            typer.echo("No trades found.")
        return

    # For a running bot, ask the engine for a fresh snapshot so current balances (-> accurate PnL) are
    # available; matches Hummingbot's history, which reads live balances.
    _request_fresh_snapshot()
    _pid = bot.read_pid()
    running = _pid is not None and bot.pid_alive(_pid)
    balances = (bot.read_status() or {}).get("balances") or {}
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
            note = "balances unavailable" + ("" if running else " (bot stopped)")
            typer.echo(f"  ({note} — start/current asset values may be approximate)")
        returns.append(m["return_pct"])
    if len(returns) > 1:
        typer.echo(f"\nAveraged Return = {sum(returns) / len(returns):.2f}%")
