#!/usr/bin/env python

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.market.bittrex.bittrex_active_order_tracker import BittrexActiveOrderTracker
from hummingbot.market.coinbase_pro.coinbase_pro_active_order_tracker import CoinbaseProActiveOrderTracker
from hummingbot.market.ddex.ddex_active_order_tracker import DDEXActiveOrderTracker
from hummingbot.market.idex.idex_active_order_tracker import IDEXActiveOrderTracker
from hummingbot.market.radar_relay.radar_relay_active_order_tracker import RadarRelayActiveOrderTracker
from hummingbot.market.bamboo_relay.bamboo_relay_active_order_tracker import BambooRelayActiveOrderTracker
from hummingbot.market.dolomite.dolomite_active_order_tracker import DolomiteActiveOrderTracker
from hummingbot.market.bitcoin_com.bitcoin_com_active_order_tracker import BitcoinComActiveOrderTracker


class OrderBookTrackerEntry:
    def __init__(self, trading_pair: str, timestamp: float, order_book: OrderBook):
        self._trading_pair = trading_pair
        self._timestamp = timestamp
        self._order_book = order_book

    def __repr__(self) -> str:
        return (
            f"OrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', "
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


class DDEXOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(
        self, trading_pair: str, timestamp: float, order_book: OrderBook, active_order_tracker: DDEXActiveOrderTracker
    ):
        self._active_order_tracker = active_order_tracker
        super(DDEXOrderBookTrackerEntry, self).__init__(trading_pair, timestamp, order_book)

    def __repr__(self) -> str:
        return (
            f"DDEXOrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', "
            f"order_book='{self._order_book}')"
        )

    @property
    def active_order_tracker(self) -> DDEXActiveOrderTracker:
        return self._active_order_tracker


class IDEXOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(
        self, trading_pair: str, timestamp: float, order_book: OrderBook, active_order_tracker: IDEXActiveOrderTracker
    ):
        self._active_order_tracker = active_order_tracker
        super(IDEXOrderBookTrackerEntry, self).__init__(trading_pair, timestamp, order_book)

    def __repr__(self) -> str:
        return (
            f"IDEXOrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', "
            f"order_book='{self._order_book}')"
        )

    @property
    def active_order_tracker(self) -> IDEXActiveOrderTracker:
        return self._active_order_tracker


class RadarRelayOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(
        self, trading_pair: str, timestamp: float, order_book: OrderBook, active_order_tracker: RadarRelayActiveOrderTracker
    ):
        self._active_order_tracker = active_order_tracker
        super(RadarRelayOrderBookTrackerEntry, self).__init__(trading_pair, timestamp, order_book)

    def __repr__(self) -> str:
        return (
            f"RadarRelayOrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', "
            f"order_book='{self._order_book}')"
        )

    @property
    def active_order_tracker(self) -> RadarRelayActiveOrderTracker:
        return self._active_order_tracker


class BambooRelayOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(
        self, trading_pair: str, timestamp: float, order_book: OrderBook, active_order_tracker: BambooRelayActiveOrderTracker
    ):
        self._active_order_tracker = active_order_tracker
        super(BambooRelayOrderBookTrackerEntry, self).__init__(trading_pair, timestamp, order_book)

    def __repr__(self) -> str:
        return (
            f"BambooRelayOrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', "
            f"order_book='{self._order_book}')"
        )

    @property
    def active_order_tracker(self) -> BambooRelayActiveOrderTracker:
        return self._active_order_tracker


class CoinbaseProOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(
        self, trading_pair: str, timestamp: float, order_book: OrderBook, active_order_tracker: CoinbaseProActiveOrderTracker
    ):
        self._active_order_tracker = active_order_tracker
        super(CoinbaseProOrderBookTrackerEntry, self).__init__(trading_pair, timestamp, order_book)

    def __repr__(self) -> str:
        return (
            f"CoinbaseProOrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', "
            f"order_book='{self._order_book}')"
        )

    @property
    def active_order_tracker(self) -> CoinbaseProActiveOrderTracker:
        return self._active_order_tracker


class DolomiteOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(self, trading_pair: str, timestamp: float, order_book: OrderBook,
                 active_order_tracker: DolomiteActiveOrderTracker):

        self._active_order_tracker = active_order_tracker
        super(DolomiteOrderBookTrackerEntry, self).__init__(trading_pair, timestamp, order_book)

    def __repr__(self) -> str:
        return f"DolomiteOrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', " \
            f"order_book='{self._order_book}')"

    @property
    def active_order_tracker(self) -> DolomiteActiveOrderTracker:
        return self._active_order_tracker


class BittrexOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(
        self, trading_pair: str, timestamp: float, order_book: OrderBook, active_order_tracker: BittrexActiveOrderTracker
    ):
        self._active_order_tracker = active_order_tracker
        super(BittrexOrderBookTrackerEntry, self).__init__(trading_pair, timestamp, order_book)

    def __repr__(self) -> str:
        return (
            f"BittrexOrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', "
            f"order_book='{self._order_book}')"
        )

    @property
    def active_order_tracker(self) -> BittrexActiveOrderTracker:
        return self._active_order_tracker


class BitcoinComOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(
        self, trading_pair: str, timestamp: float, order_book: OrderBook, active_order_tracker: BitcoinComActiveOrderTracker
    ):
        self._active_order_tracker = active_order_tracker
        super(BitcoinComOrderBookTrackerEntry, self).__init__(trading_pair, timestamp, order_book)

    def __repr__(self) -> str:
        return (
            f"BitcoinComOrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', "
            f"order_book='{self._order_book}')"
        )

    @property
    def active_order_tracker(self) -> BitcoinComActiveOrderTracker:
        return self._active_order_tracker

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
    def trading_pair(self) -> (str):
        return self._trading_pair

    @property
    def timestamp(self) -> (float):
        return self._timestamp

    @property
    def order_book(self) -> (OrderBook):
        return self._order_book