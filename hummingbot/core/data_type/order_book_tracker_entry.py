#!/usr/bin/env python

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.market.coinbase_pro.coinbase_pro_active_order_tracker import CoinbaseProActiveOrderTracker
from hummingbot.market.ddex.ddex_active_order_tracker import DDEXActiveOrderTracker
from hummingbot.market.idex.idex_active_order_tracker import IDEXActiveOrderTracker
from hummingbot.market.radar_relay.radar_relay_active_order_tracker import RadarRelayActiveOrderTracker
from hummingbot.market.bamboo_relay.bamboo_relay_active_order_tracker import BambooRelayActiveOrderTracker


class OrderBookTrackerEntry:
    def __init__(self, symbol: str, timestamp: float, order_book: OrderBook):
        self._symbol = symbol
        self._timestamp = timestamp
        self._order_book = order_book

    def __repr__(self) -> str:
        return f"OrderBookTrackerEntry(symbol='{self._symbol}', timestamp='{self._timestamp}', " \
               f"order_book='{self._order_book}')"

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def timestamp(self) -> float:
        return self._timestamp

    @property
    def order_book(self) -> OrderBook:
        return self._order_book


class DDEXOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(self, symbol: str, timestamp: float, order_book: OrderBook,
                 active_order_tracker: DDEXActiveOrderTracker):
        self._active_order_tracker = active_order_tracker
        super(DDEXOrderBookTrackerEntry, self).__init__(symbol, timestamp, order_book)

    def __repr__(self) -> str:
        return f"DDEXOrderBookTrackerEntry(symbol='{self._symbol}', timestamp='{self._timestamp}', " \
               f"order_book='{self._order_book}')"

    @property
    def active_order_tracker(self) -> DDEXActiveOrderTracker:
        return self._active_order_tracker


class IDEXOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(self, symbol: str, timestamp: float, order_book: OrderBook,
                 active_order_tracker: IDEXActiveOrderTracker):
        self._active_order_tracker = active_order_tracker
        super(IDEXOrderBookTrackerEntry, self).__init__(symbol, timestamp, order_book)

    def __repr__(self) -> str:
        return f"IDEXOrderBookTrackerEntry(symbol='{self._symbol}', timestamp='{self._timestamp}', " \
               f"order_book='{self._order_book}')"

    @property
    def active_order_tracker(self) -> IDEXActiveOrderTracker:
        return self._active_order_tracker


class RadarRelayOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(self, symbol: str, timestamp: float, order_book: OrderBook,
                 active_order_tracker: RadarRelayActiveOrderTracker):
        self._active_order_tracker = active_order_tracker
        super(RadarRelayOrderBookTrackerEntry, self).__init__(symbol, timestamp, order_book)

    def __repr__(self) -> str:
        return f"RadarRelayOrderBookTrackerEntry(symbol='{self._symbol}', timestamp='{self._timestamp}', " \
               f"order_book='{self._order_book}')"

    @property
    def active_order_tracker(self) -> RadarRelayActiveOrderTracker:
        return self._active_order_tracker


class BambooRelayOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(self, symbol: str, timestamp: float, order_book: OrderBook,
                 active_order_tracker: BambooRelayActiveOrderTracker):
        self._active_order_tracker = active_order_tracker
        super(BambooRelayOrderBookTrackerEntry, self).__init__(symbol, timestamp, order_book)

    def __repr__(self) -> str:
        return f"BambooRelayOrderBookTrackerEntry(symbol='{self._symbol}', timestamp='{self._timestamp}', " \
               f"order_book='{self._order_book}')"

    @property
    def active_order_tracker(self) -> BambooRelayActiveOrderTracker:
        return self._active_order_tracker


class CoinbaseProOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(self, symbol: str, timestamp: float, order_book: OrderBook,
                 active_order_tracker: CoinbaseProActiveOrderTracker):
        self._active_order_tracker = active_order_tracker
        super(CoinbaseProOrderBookTrackerEntry, self).__init__(symbol, timestamp, order_book)

    def __repr__(self) -> str:
        return f"CoinbaseProOrderBookTrackerEntry(symbol='{self._symbol}', timestamp='{self._timestamp}', " \
               f"order_book='{self._order_book}')"

    @property
    def active_order_tracker(self) -> CoinbaseProActiveOrderTracker:
        return self._active_order_tracker


class BittrexOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(self, symbol: str, timestamp: float, order_book: OrderBook,
                 active_order_tracker=None):
        super(BittrexOrderBookTrackerEntry, self).__init__(symbol, timestamp, order_book)

    def __repr__(self) -> str:
        return f"BittrexOrderBookTrackerEntry(symbol='{self._symbol}', timestamp='{self._timestamp}', " \
               f"order_book='{self._order_book}')"

    @property
    def active_order_tracker(self):
        return NotImplementedError
