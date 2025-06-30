import asyncio
from decimal import Decimal
from typing import List, Optional, Set, Tuple

import pandas as pd
import psutil
import tabulate

from hummingbot.client.config.config_data_types import ClientConfigEnum
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.model.trade_fill import TradeFill

s_decimal_0 = Decimal("0")


def format_bytes(size):
    for unit in ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB"]:
        if abs(size) < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} YB"


async def start_timer(timer):
    count = 1
    while True:
        count += 1

        mins, sec = divmod(count, 60)
        hour, mins = divmod(mins, 60)
        days, hour = divmod(hour, 24)

        timer.log(f"Uptime: {days:>3} day(s), {hour:02}:{mins:02}:{sec:02}")
        await _sleep(1)


async def _sleep(delay):
    """
    A wrapper function that facilitates patching the sleep in unit tests without affecting the asyncio module
    """
    await asyncio.sleep(delay)


async def start_process_monitor(process_monitor):
    hb_process = psutil.Process()
    while True:
        with hb_process.oneshot():
            threads = hb_process.num_threads()
            process_monitor.log("CPU: {:>5}%, ".format(hb_process.cpu_percent()) +
                                "Mem: {:>10} ({}), ".format(
                                    format_bytes(hb_process.memory_info().vms / threads),
                                    format_bytes(hb_process.memory_info().rss)) +
                                "Threads: {:>3}, ".format(threads)
                                )
        await _sleep(1)


async def start_trade_monitor(trade_monitor):
    from hummingbot.client.hummingbot_application import HummingbotApplication
    hb = HummingbotApplication.main_application()
    trade_monitor.log("Trades: 0, Total P&L: 0.00, Return %: 0.00%")
    return_pcts = []
    pnls = []

    while True:
        try:
            if hb.trading_core._strategy_running and hb.trading_core.strategy is not None:
                if all(market.ready for market in hb.trading_core.markets.values()):
                    with hb.trading_core.trade_fill_db.get_new_session() as session:
                        trades: List[TradeFill] = hb._get_trades_from_session(
                            int(hb.init_time * 1e3),
                            session=session,
                            config_file_path=hb.strategy_file_name)
                        if len(trades) > 0:
                            market_info: Set[Tuple[str, str]] = set((t.market, t.symbol) for t in trades)
                            for market, symbol in market_info:
                                cur_trades = [t for t in trades if t.market == market and t.symbol == symbol]
                                cur_balances = await hb.get_current_balances(market)
                                perf = await PerformanceMetrics.create(symbol, cur_trades, cur_balances)
                                return_pcts.append(perf.return_pct)
                                pnls.append(perf.total_pnl)
                            avg_return = sum(return_pcts) / len(return_pcts) if len(return_pcts) > 0 else s_decimal_0
                            quote_assets = set(t.symbol.split("-")[1] for t in trades)
                            if len(quote_assets) == 1:
                                total_pnls = f"{PerformanceMetrics.smart_round(sum(pnls))} {list(quote_assets)[0]}"
                            else:
                                total_pnls = "N/A"
                            trade_monitor.log(f"Trades: {len(trades)}, Total P&L: {total_pnls}, "
                                              f"Return %: {avg_return:.2%}")
                            return_pcts.clear()
                            pnls.clear()
            await _sleep(2)  # sleeping for longer to manage resources
        except asyncio.CancelledError:
            raise
        except Exception:
            hb.logger().exception("start_trade_monitor failed.")


def format_df_for_printout(
    df: pd.DataFrame, table_format: ClientConfigEnum, max_col_width: Optional[int] = None, index: bool = False
) -> str:
    if max_col_width is not None:  # in anticipation of the next release of tabulate which will include maxcolwidth
        max_col_width = max(max_col_width, 4)
        df = df.astype(str).apply(
            lambda s: s.apply(
                lambda e: e if len(e) < max_col_width else f"{e[:max_col_width - 3]}..."
            )
        )
        df.columns = [c if len(c) < max_col_width else f"{c[:max_col_width - 3]}..." for c in df.columns]

    original_preserve_whitespace = tabulate.PRESERVE_WHITESPACE
    tabulate.PRESERVE_WHITESPACE = True
    try:
        formatted_df = tabulate.tabulate(df, tablefmt=table_format, showindex=index, headers="keys")
    finally:
        tabulate.PRESERVE_WHITESPACE = original_preserve_whitespace
    return formatted_df
