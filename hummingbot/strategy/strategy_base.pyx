from typing import List
from wings.time_iterator cimport TimeIterator
from wings.market.market_base cimport MarketBase
from wings.event_logger cimport EventLogger
from wings.trade import Trade
from wings.events import OrderFilledEvent


cdef class StrategyBase(TimeIterator):
    def __init__(self):
        super().__init__()

    @property
    def active_markets(self) -> List[MarketBase]:
        raise NotImplementedError

    def format_status(self):
        raise NotImplementedError

    @property
    def trades(self) -> List[Trade]:
        def event_to_trade(order_filled_event: OrderFilledEvent, market_name: str):
            return Trade(order_filled_event.symbol,
                         order_filled_event.trade_type,
                         order_filled_event.price,
                         order_filled_event.amount,
                         order_filled_event.order_type,
                         market_name,
                         order_filled_event.timestamp)

        past_trades = []
        for market in self.active_markets:
            event_logs = market.event_logs
            order_filled_events = list(filter(lambda e: isinstance(e, OrderFilledEvent), event_logs))
            past_trades += list(map(lambda ofe: event_to_trade(ofe, market.__class__.__name__), order_filled_events))

        return sorted(past_trades, key=lambda x: x.timestamp)
