# distutils: language=c++

from typing import Union, List, Tuple

from hummingbot.core.clock import Clock
from hummingbot.core.clock cimport Clock
from hummingbot.strategy.pure_market_making import PureMarketMakingStrategy
from hummingbot.core.event.events import (
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderFilledEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderExpiredEvent,
    MarketEvent,
    TradeFee
)
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.market.market_base import MarketBase
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order

cdef class ScriptIterator(TimeIterator):
    start_script_start_marker = "#### Start Script"
    tick_script_start_marker = "#### Tick Script"
    buy_order_completed_script_start_marker = "#### Buy Order Completed Event"
    sell_order_completed_script_start_marker = "#### Sell Order Completed Event"

    def __init__(self,
                 script_file_name: str,
                 markets: List[MarketBase],
                 strategy: PureMarketMakingStrategy):
        super().__init__()
        self._strategy = strategy
        self._markets = markets
        self._variables = {}
        self.read_script_file(script_file_name)
        self._did_complete_buy_order_forwarder = SourceInfoEventForwarder(self._did_complete_buy_order)
        self._did_complete_sell_order_forwarder = SourceInfoEventForwarder(self._did_complete_sell_order)
        self._event_pairs = [
            (MarketEvent.BuyOrderCompleted, self._did_complete_buy_order_forwarder),
            (MarketEvent.SellOrderCompleted, self._did_complete_sell_order_forwarder)
        ]

    def read_script_file(self, script_file_name: str):
        file = open(script_file_name, "r")
        start_scripts, tick_scripts, buy_completed_scripts, sell_completed_scripts = [], [], [], []
        scripts = None
        for line in file:
            if line.strip() == "":
                continue
            elif self.start_script_start_marker in line:
                scripts = start_scripts
                continue
            elif self.tick_script_start_marker in line:
                scripts = tick_scripts
                continue
            elif self.buy_order_completed_script_start_marker in line:
                scripts = buy_completed_scripts
                continue
            elif self.sell_order_completed_script_start_marker in line:
                scripts = sell_completed_scripts
                continue
            scripts.append(line)
        self._start_script = "".join(start_scripts)
        self._tick_script = "".join(tick_scripts)
        self._buy_order_completed_script = "".join(buy_completed_scripts)
        self._sell_order_completed_script = "".join(sell_completed_scripts)

    @property
    def tick_script(self):
        return self._tick_script

    @property
    def strategy(self):
        return self._strategy

    @property
    def variables(self):
        return self._variables

    # def run_start(self):
    #     print("script_iterator starts")
    #     print(f"_start_script {self._start_script}")
    #     exec(self._start_script, self.global_map())

    cdef c_start(self, Clock clock, double timestamp):
        TimeIterator.c_start(self, clock, timestamp)
        for market in self._markets:
            for event_pair in self._event_pairs:
                market.add_listener(event_pair[0], event_pair[1])
        exec(self._start_script, self.global_map())

    def tick(self, double timestamp):
        exec(self._tick_script, self.global_map())

    cdef c_tick(self, double timestamp):
        TimeIterator.c_tick(self, timestamp)
        self.tick(timestamp)

    def global_map(self):
        return {'strategy': self.strategy, 'variables': self.variables}

    def _did_complete_buy_order(self,
                                event_tag: int,
                                market: MarketBase,
                                event: BuyOrderCompletedEvent):
        exec(self._buy_order_completed_script, self.global_map(), {'event': event})

    def _did_complete_sell_order(self,
                                 event_tag: int,
                                 market: MarketBase,
                                 event: SellOrderCompletedEvent):
        exec(self._sell_order_completed_script, self.global_map(), {'event': event})
