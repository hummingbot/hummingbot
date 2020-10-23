import psutil
import datetime
import asyncio


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
                                "Threads: {:>3}".format(threads)
                                )
        await asyncio.sleep(1)


async def start_trade_monitor(trade_monitor):
    from hummingbot.client.hummingbot_application import HummingbotApplication
    hb = HummingbotApplication.main_application()
    trade_monitor.log("Trades: 0, Performance: 0.00%")
    while True:
        if hb.strategy_task is not None and not hb.strategy_task.done():
            if all(market.ready for market in hb.markets.values()):
                performance, _ = hb._calculate_trade_performance()
                trade_monitor.log(f"Trades: {performance['no_of_trades']}, Performance: {performance['portfolio_delta_percentage']}%")
        await asyncio.sleep(3)  # sleeping for longer to manage resources
