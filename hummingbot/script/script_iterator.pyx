# distutils: language=c++

from typing import List
import asyncio
import logging
import traceback
from multiprocessing import Process, Queue
from hummingbot.core.clock cimport Clock
from hummingbot.core.clock import Clock
from hummingbot.strategy.pure_market_making import PureMarketMakingStrategy
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    MarketEvent,
)
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.script.script_process import run_script
from hummingbot.script.script_interface import (
    StrategyParameter,
    PMMParameters,
    OnTick,
    OnStatus,
    OnCommand,
    CallNotify,
    CallLog,
    PmmMarketInfo,
    ScriptError,
)

sir_logger = None


cdef class ScriptIterator(TimeIterator):
    @classmethod
    def logger(cls):
        global sir_logger
        if sir_logger is None:
            sir_logger = logging.getLogger(__name__)
        return sir_logger

    def __init__(self,
                 script_file_path: str,
                 markets: List[ExchangeBase],
                 strategy: PureMarketMakingStrategy,
                 queue_check_interval: float = 0.01,
                 is_unit_testing_mode: bool = False):
        super().__init__()
        self._script_file_path = script_file_path
        self._markets = markets
        self._strategy = strategy
        self._is_unit_testing_mode = is_unit_testing_mode
        self._queue_check_interval = queue_check_interval
        self._did_complete_buy_order_forwarder = SourceInfoEventForwarder(self._did_complete_buy_order)
        self._did_complete_sell_order_forwarder = SourceInfoEventForwarder(self._did_complete_sell_order)
        self._event_pairs = [
            (MarketEvent.BuyOrderCompleted, self._did_complete_buy_order_forwarder),
            (MarketEvent.SellOrderCompleted, self._did_complete_sell_order_forwarder)
        ]
        self._ev_loop = asyncio.get_event_loop()
        self._parent_queue = Queue()
        self._child_queue = Queue()
        self._listen_to_child_task = safe_ensure_future(self.listen_to_child_queue(), loop=self._ev_loop)

        self._script_process = Process(
            target=run_script,
            args=(script_file_path, self._parent_queue, self._child_queue, queue_check_interval,)
        )
        self.logger().info(f"starting script in {script_file_path}")
        self._script_process.start()

    @property
    def strategy(self):
        return self._strategy

    cdef c_start(self, Clock clock, double timestamp):
        TimeIterator.c_start(self, clock, timestamp)
        for market in self._markets:
            for event_pair in self._event_pairs:
                market.add_listener(event_pair[0], event_pair[1])
        self._parent_queue.put(PmmMarketInfo(self._strategy.market_info.market.name,
                                             self._strategy.trading_pair))

    cdef c_stop(self, Clock clock):
        TimeIterator.c_stop(self, clock)
        self._parent_queue.put(None)
        self._child_queue.put(None)
        self._script_process.join()
        if self._listen_to_child_task is not None:
            self._listen_to_child_task.cancel()

    cdef c_tick(self, double timestamp):
        TimeIterator.c_tick(self, timestamp)
        if not self._strategy.all_markets_ready():
            return
        cdef object pmm_strategy = PMMParameters()
        for attr in PMMParameters.__dict__.keys():
            if attr[:1] != '_':
                param_value = getattr(self._strategy, attr)
                setattr(pmm_strategy, attr, param_value)
        cdef object on_tick = OnTick(self.strategy.get_mid_price(), pmm_strategy,
                                     self.all_total_balances(), self.all_available_balances())
        self._parent_queue.put(on_tick)

    def _did_complete_buy_order(self,
                                event_tag: int,
                                market: ExchangeBase,
                                event: BuyOrderCompletedEvent):
        self._parent_queue.put(event)

    def _did_complete_sell_order(self,
                                 event_tag: int,
                                 market: ExchangeBase,
                                 event: SellOrderCompletedEvent):
        self._parent_queue.put(event)

    async def listen_to_child_queue(self):
        while True:
            try:
                if self._child_queue.empty():
                    await asyncio.sleep(self._queue_check_interval)
                    continue
                item = self._child_queue.get()
                if item is None:
                    break
                if isinstance(item, StrategyParameter):
                    self.logger().info(f"received: {str(item)}")
                    setattr(self._strategy, item.name, item.updated_value)
                elif isinstance(item, CallNotify) and not self._is_unit_testing_mode:
                    # ignore this on unit testing as the below import will mess up unit testing.
                    from hummingbot.client.hummingbot_application import HummingbotApplication
                    HummingbotApplication.main_application()._notify(item.msg)
                elif isinstance(item, CallLog):
                    self.logger().info(f"script - {item.msg}")
                elif isinstance(item, ScriptError):
                    self.logger().info(f"{item}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().info("Unexpected error listening to child queue.", exc_info=True)

    def request_status(self):
        self._parent_queue.put(OnStatus())

    def request_command(self, cmd: str, args: List[str]):
        self._parent_queue.put(OnCommand(cmd, args))

    def all_total_balances(self):
        all_bals = {m.name: m.get_all_balances() for m in self._markets}
        return {exchange: {token: bal for token, bal in bals.items() if bal > 0} for exchange, bals in all_bals.items()}

    def all_available_balances(self):
        all_bals = self.all_total_balances()
        ret_val = {}
        for exchange, balances in all_bals.items():
            connector = [c for c in self._markets if c.name == exchange][0]
            ret_val[exchange] = {token: connector.get_available_balance(token) for token in balances.keys()}
        return ret_val
