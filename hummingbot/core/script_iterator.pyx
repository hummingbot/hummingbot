# distutils: language=c++

from typing import Union, List, Tuple
import importlib.util

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
        self._script_module = self.import_script_module(script_file_name)
        self._did_complete_buy_order_forwarder = SourceInfoEventForwarder(self._did_complete_buy_order)
        self._did_complete_sell_order_forwarder = SourceInfoEventForwarder(self._did_complete_sell_order)
        self._event_pairs = [
            (MarketEvent.BuyOrderCompleted, self._did_complete_buy_order_forwarder),
            (MarketEvent.SellOrderCompleted, self._did_complete_sell_order_forwarder)
        ]

    def import_script_module(self, script_file_name: str):
        spec = importlib.util.spec_from_file_location("price_band_script", script_file_name)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @property
    def tick_script(self):
        return self._tick_script

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
        # exec(self._start_script, self.global_map())

    def tick(self, double timestamp):
        self._script_module.tick(self.strategy)

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
