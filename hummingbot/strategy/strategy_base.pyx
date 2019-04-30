from typing import List
from wings.clock cimport Clock
from wings.time_iterator cimport TimeIterator
from wings.market.market_base cimport MarketBase
from wings.trade import Trade
from wings.event_listener cimport EventListener
from wings.events import MarketEvent


cdef class OrderFilledListener(EventListener):
    cdef:
        StrategyBase _owner

    def __init__(self, StrategyBase owner):
        super().__init__()
        self._owner = owner

    cdef c_call(self, object arg):
        self._owner.c_record_trade(arg)


cdef class StrategyBase(TimeIterator):
    def __init__(self):
        super().__init__()
        self._past_trades = []
        self._trade_listener = OrderFilledListener(self)

    @property
    def active_markets(self) -> List[MarketBase]:
        raise NotImplementedError

    def format_status(self):
        raise NotImplementedError

    @property
    def trades(self) -> List[Trade]:
        return self._past_trades

    cdef c_record_trade(self, object order_filled_event):
        self._past_trades.append(
            Trade(order_filled_event.symbol,
                  order_filled_event.trade_type,
                  order_filled_event.price,
                  order_filled_event.amount))

    cdef c_start(self, Clock clock, double timestamp):
        cdef:
            MarketBase typed_market

        TimeIterator.c_start(self, clock, timestamp)
        for active_market in self.active_markets:
            typed_market = active_market
            typed_market.c_add_listener(MarketEvent.OrderFilled.value, self._trade_listener)

    def stop(self):
        pass