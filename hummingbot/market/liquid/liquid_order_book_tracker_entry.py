#!/usr/bin/env python

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry


class LiquidOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(self, trading_pair: str, timestamp: float, order_book: OrderBook):
        self._trading_pair = trading_pair
        self._timestamp = timestamp
        self._order_book = order_book

    def __repr__(self) -> (str):
        return (
            f"LiquidOrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', "
            f"order_book='{self._order_book}')"
        )

    @property
    def trading_pair(self) -> str:
        return self._trading_pair

    @property
    def timestamp(self) -> float:
        return self._timestamp

    @property
    def order_book(self) -> OrderBook:
        return self._order_book
