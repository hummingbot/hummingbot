from decimal import Decimal
from typing import (
    Set,
    Tuple,
    List
)
import psutil
import datetime
import asyncio
from hummingbot.model.trade_fill import TradeFill
from hummingbot.client.performance import PerformanceMetrics


s_decimal_0 = Decimal("0")


def format_bytes(size):
    power = 1000
    n = 0
    power_labels = {0: '', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size > power:
        size /= power
        n += 1
    return f"{round(size, 2)} {power_labels[n]}"


async def start_timer(timer):
    count = 1
    while True:
        count += 1
        timer.log(f"Duration: {datetime.timedelta(seconds=count)}")
        await asyncio.sleep(1)


async def start_process_monitor(process_monitor):
    hb_process = psutil.Process()
    while True:
        with hb_process.oneshot():
            threads = hb_process.num_threads()
            process_monitor.log("CPU: {:>5}%, ".format(hb_process.cpu_percent()) +
                                "Mem: {:>10}, ".format(format_bytes(hb_process.memory_info()[1] / threads)) +
                                "Threads: {:>3}, ".format(threads)
                                )
        await asyncio.sleep(1)


async def start_trade_monitor(trade_monitor):
    from hummingbot.client.hummingbot_application import HummingbotApplication
    hb = HummingbotApplication.main_application()
    trade_monitor.log("Trades: 0, Total P&L: 0.00, Return %: 0.00%")
    total_trades = 0
    return_pcts = []
    pnls = []
    quote_asset = ""

    while True:
        if hb.strategy_task is not None and not hb.strategy_task.done():
            if all(market.ready for market in hb.markets.values()):
                trades: List[TradeFill] = hb._get_trades_from_session(int(hb.init_time * 1e3),
                                                                      config_file_path=hb.strategy_file_name)
                if len(trades) > total_trades:
                    total_trades = len(trades)
                    market_info: Set[Tuple[str, str]] = set((t.market, t.symbol) for t in trades)
                    for market, symbol in market_info:
                        quote_asset = symbol.split("-")[1]  # Note that the qiote asset of the last pair is assumed to be the quote asset of P&L for simplicity
                        cur_trades = [t for t in trades if t.market == market and t.symbol == symbol]
                        cur_balances = await hb.get_current_balances(market)
                        perf = await PerformanceMetrics.create(market, symbol, cur_trades, cur_balances)
                        return_pcts.append(perf.return_pct)
                        pnls.append(perf.total_pnl)
                    avg_return = sum(return_pcts) / len(return_pcts) if len(return_pcts) > 0 else s_decimal_0
                    total_pnls = sum(pnls)  # Note that this sum doesn't handles cases with different multiple pairs for simplisity
                    trade_monitor.log(f"Trades: {total_trades}, Total P&L: {PerformanceMetrics.smart_round(total_pnls)} {quote_asset}, Return %: {avg_return:.2%}")
                    return_pcts.clear()
                    pnls.clear()
        await asyncio.sleep(2)  # sleeping for longer to manage resources
