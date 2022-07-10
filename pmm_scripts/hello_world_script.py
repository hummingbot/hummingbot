import inspect
import pprint
import time
from datetime import datetime
from os import getcwd
from os.path import join, realpath

from hummingbot.core.management.diagnosis import active_tasks
from hummingbot.core.rate_oracle.rate_oracle import RateOracle, RateOracleSource
from hummingbot.pmm_script.pmm_script_base import PMMScriptBase


def print_frames(frame_list):
    stack_str = ''
    module_frame_index = [i for i, f in enumerate(frame_list) if f.function == '<module>'][0]
    for i in range(module_frame_index):
        d = frame_list[i][0].f_locals
        local_vars = {x: d[x] for x in d}
        stack_str = stack_str + f"       [Frame {module_frame_index - i} '{frame_list[i].function}': {local_vars}]\n"
    return stack_str + "        [Frame '<module>']\n"


LOGS_PATH = realpath(join(getcwd(), "logs/"))
SCRIPT_LOG_FILE = f"{LOGS_PATH}/debug_rates_in_pmm_script.log"


def log_to_file(file_name, message):
    with open(file_name, "a+") as f:
        # pprint.pprint(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " - " + message + "\n", stream=f)
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " - " + message + "\n")


class HelloWorldPMMScript(PMMScriptBase):
    """
    Demonstrates how to send messages using notify and log functions. It also shows how errors and commands are handled.
    """

    def __init__(self):
        super().__init__()
        self._last_async_refresh_ts = 0
        self.rate_future = None
        self.oracles = [RateOracleSource.kucoin, RateOracleSource.ascend_ex,
                        RateOracleSource.coingecko, RateOracleSource.binance]

    async def print_rates_async(self, source: RateOracleSource):
        RateOracle.source = source
        self.log(
            f"   {time.time()} {RateOracle.source:30s} Price: BTC-USD ->  {await RateOracle.rate_async('BTC-USD')}")
        self.log(
            f"   {time.time()} {RateOracle.source:30s} Price: BTC-USDT -> {await (RateOracle.rate_async('BTC-USDT'))}")

    def print_rates(self):
        if self.rate_future:
            if self.rate_future.done():
                try:
                    log_to_file(SCRIPT_LOG_FILE,
                                f"   Call to async price refresh done {RateOracle.source:30s} Price: BTC-USD ->  {self.rate_future.result()}")
                except RuntimeError:
                    log_to_file(SCRIPT_LOG_FILE,
                                "   Ok, there must be a conflict with the HB call")

                self.rate_future = None
                oracle_inst = RateOracle.get_instance()
                rate_usd = oracle_inst.rate('BTC-USD')
                rate_usdt = oracle_inst.rate('BTC-USDT')
                log_to_file(SCRIPT_LOG_FILE,
                            f" After async call  {RateOracle.source:30s} Price: BTC-USD ->  {rate_usd}")
                log_to_file(SCRIPT_LOG_FILE,
                            f" After async call  {RateOracle.source:30s} Price: BTC-USDT -> {rate_usdt}")
            else:
                log_to_file(SCRIPT_LOG_FILE,
                            f" Waiting for async call completion:{self.rate_future}")

        else:
            oracle_inst = RateOracle.get_instance()
            log_to_file(SCRIPT_LOG_FILE,
                        f" PMM script -     instance:{hex(id(oracle_inst))}\n\t{repr(oracle_inst)}\n\t{pprint.pformat(vars(oracle_inst), indent=10, depth=1)}")
            rate_usdt = oracle_inst.rate('BTC-USDT')
            log_to_file(SCRIPT_LOG_FILE, f" PMM script - inst:{repr(oracle_inst)}")
            log_to_file(SCRIPT_LOG_FILE, f" PMM script - Price: BTC-USDT -> {rate_usdt}")
            log_to_file(SCRIPT_LOG_FILE, f" PMM script - Price from parent: BTC-USDT -> {self.rate('BTC-USDT')}")
            # tasks_df = active_tasks().copy().reset_index()
            # log_to_file(SCRIPT_LOG_FILE, f"   HB Task list\n\t{tasks_df[tasks_df.func_name == 'RateOracle.rate_async()']}")
            # if tasks_df[tasks_df.func_name == 'RateOracle.rate_async()'].empty:
            #    self.rate_future = asyncio.run_coroutine_threadsafe(RateOracle.rate_async('BTC-USD'),
            #                                                    asyncio.get_event_loop())
            # else:
            #    log_to_file(SCRIPT_LOG_FILE,
            #                f"   Ooops, called by HB \n\t{tasks_df[tasks_df.func_name == 'RateOracle.rate_async()']}")

    def on_tick(self):
        log_to_file(SCRIPT_LOG_FILE, "*** on_tick()")
        log_to_file(SCRIPT_LOG_FILE, print_frames(inspect.stack()))

        # if self._last_async_refresh_ts < (time.time() - 10):
        tasks_df = active_tasks().copy().reset_index()

        if not tasks_df[tasks_df.func_name == 'RateOracle.rate_async()'].empty:
            log_to_file(SCRIPT_LOG_FILE,
                        f" Waiting for rate_async called by hummingbot to be completed {tasks_df}")
            log_to_file(SCRIPT_LOG_FILE,
                        f" Waiting for rate_async called by hummingbot to be completed {tasks_df[tasks_df.func_name == 'RateOracle.rate_async()']}")
            log_to_file(SCRIPT_LOG_FILE,
                        f" Waiting for rate_async called by hummingbot to be completed {tasks_df[tasks_df.func_name == 'RateOracle.rate_async()'].empty}")
            return

        if (not self.rate_future or self.rate_future.done()) and self.oracles:
            # source = self.oracles.pop(0)
            self.print_rates()
        elif not self.oracles:
            self.oracles = [RateOracleSource.kucoin, RateOracleSource.ascend_ex,
                            RateOracleSource.coingecko, RateOracleSource.binance]
        # else:
        #    log_to_file(SCRIPT_LOG_FILE,
        #                f" Waiting for async call completion: {self.rate_future.done()}\n\t{self.rate_future}\n\t{self.oracles} empty")
        # self._last_async_refresh_ts = time.time()
        log_to_file(SCRIPT_LOG_FILE, "*** Exiting on_tick()")

    def on_command(self, cmd, args):
        if cmd == 'ping':
            self.notify('pong!')
        else:
            self.notify(f'Unrecognised command: {cmd}')

    def on_status(self):
        log_to_file(SCRIPT_LOG_FILE, "*** on_status()")
        # if self._last_async_refresh_ts < (time.time() - 10):
        tasks_df = active_tasks().copy().reset_index()

        if not tasks_df[tasks_df.func_name == 'RateOracle.rate_async()'].empty:
            log_to_file(SCRIPT_LOG_FILE,
                        f" Waiting for rate_async called by hummingbot to be completed {tasks_df}")
            log_to_file(SCRIPT_LOG_FILE,
                        f" Waiting for rate_async called by hummingbot to be completed {tasks_df[tasks_df.func_name == 'RateOracle.rate_async()']}")
            log_to_file(SCRIPT_LOG_FILE,
                        f" Waiting for rate_async called by hummingbot to be completed {tasks_df[tasks_df.func_name == 'RateOracle.rate_async()'].empty}")
            return

        if (not self.rate_future or self.rate_future.done()) and self.oracles:
            source = self.oracles.pop(0)
            self.print_rates(source)
        elif not self.oracles:
            self.oracles = [RateOracleSource.kucoin, RateOracleSource.ascend_ex,
                            RateOracleSource.coingecko, RateOracleSource.binance]
        # else:
        #    log_to_file(SCRIPT_LOG_FILE,
        #                f" Waiting for async call completion: {self.rate_future.done()}\n\t{self.rate_future}\n\t{self.oracles} empty")
        # self._last_async_refresh_ts = time.time()
        log_to_file(SCRIPT_LOG_FILE, "*** Exiting on_status()")
        return "*** Exiting on_status()"
