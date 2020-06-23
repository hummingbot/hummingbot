# distutils: language=c++

from typing import List
import asyncio
from multiprocessing import Process, Queue
from hummingbot.core.clock import Clock
from hummingbot.core.clock cimport Clock
from hummingbot.strategy.pure_market_making import PureMarketMakingStrategy
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    MarketEvent,
)
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.market.market_base import MarketBase
from hummingbot.script.script_process import run_script
from hummingbot.script.script_interface import (
    OnTick,
    CallUpdateStrategyParameters,
    StrategyParameters
)

cdef class ScriptIterator(TimeIterator):

    def __init__(self,
                 script_file_name: str,
                 markets: List[MarketBase],
                 strategy: PureMarketMakingStrategy):
        super().__init__()
        self._strategy = strategy
        self._markets = markets
        self._variables = {}
        # self._script_module = self.import_script_module(script_file_name)
        self._did_complete_buy_order_forwarder = SourceInfoEventForwarder(self._did_complete_buy_order)
        self._did_complete_sell_order_forwarder = SourceInfoEventForwarder(self._did_complete_sell_order)
        self._event_pairs = [
            (MarketEvent.BuyOrderCompleted, self._did_complete_buy_order_forwarder),
            (MarketEvent.SellOrderCompleted, self._did_complete_sell_order_forwarder)
        ]
        self._ev_loop = asyncio.get_event_loop()
        self._parent_queue = Queue()
        self._child_queue = Queue()
        # self._listen_to_child_task = None
        print("starting listener")
        print(f"ev_loop running: {self._ev_loop.is_running()}")
        safe_ensure_future(self.listen_to_child_queue(), loop=self._ev_loop)

        self._script_process = Process(target=run_script, args=(self._parent_queue, self._child_queue,))
        self._script_process.start()

    async def start_listener(self):
        self._listen_to_child_task = safe_ensure_future(self.listen_to_child_queue(), loop=self._ev_loop)

    @property
    def strategy(self):
        return self._strategy

    @property
    def variables(self):
        return self._variables

    cdef c_start(self, Clock clock, double timestamp):
        TimeIterator.c_start(self, clock, timestamp)
        for market in self._markets:
            for event_pair in self._event_pairs:
                market.add_listener(event_pair[0], event_pair[1])

    cdef c_stop(self, Clock clock):
        TimeIterator.c_stop(self, clock)
        self._parent_queue.put(None)
        self._child_queue.put(None)
        self._script_process.join()
        if self._listen_to_child_task is not None:
            self._listen_to_child_task.cancel()

    def tick(self, double timestamp):
        on_tick = OnTick(self.strategy.get_mid_price(), StrategyParameters(
            self.strategy.buy_levels, self.strategy.sell_levels, self.strategy.order_levels))
        self._parent_queue.put(on_tick)

    cdef c_tick(self, double timestamp):
        TimeIterator.c_tick(self, timestamp)
        self.tick(timestamp)

    def global_map(self):
        return {'strategy': self.strategy, 'variables': self.variables}

    def _did_complete_buy_order(self,
                                event_tag: int,
                                market: MarketBase,
                                event: BuyOrderCompletedEvent):
        pass

    def _did_complete_sell_order(self,
                                 event_tag: int,
                                 market: MarketBase,
                                 event: SellOrderCompletedEvent):
        pass

    async def listen_to_child_queue(self):
        while True:
            if self._child_queue.empty():
                await asyncio.sleep(0.1)
                continue
            item = self._child_queue.get()
            print(f"parent gets {item.__class__}")
            if item is None:
                break
            if isinstance(item, CallUpdateStrategyParameters):
                self._strategy.buy_levels = item.strategy_parameters.buy_levels
                self._strategy.sell_levels = item.strategy_parameters.sell_levels
                self._strategy.order_levels = item.strategy_parameters.order_levels
