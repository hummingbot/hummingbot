from typing import List, Dict, Tuple
import asyncio
from decimal import Decimal
from hummingbot.connector.exchange.paper_trade import PaperTradeExchange
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker, OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book import OrderBook, OrderBookRow
from hummingbot.core.data_type.composite_order_book import CompositeOrderBook


class MockOrderBookTrackerDataSource(OrderBookTrackerDataSource):
    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        pass

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        pass

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass


class MockOrderTracker(OrderBookTracker):
    def __init__(self, trading_pairs: List[str]):
        self._data_source: MockOrderBookTrackerDataSource = MockOrderBookTrackerDataSource(trading_pairs)
        self._trading_pairs: List[str] = trading_pairs
        self._order_books: Dict[str, OrderBook] = {}

    def exchange_name(self):
        return str(self.__class__)

    @property
    def ready(self) -> bool:
        return True

    def start(self):
        pass

    def stop(self):
        pass


class MockPaperTradeExchange(PaperTradeExchange):

    def split_trading_pair(self, trading_pair: str) -> Tuple[str, str]:
        return trading_pair.split("-")

    def set_balanced_order_book(self, trading_pair: str, mid_price: Decimal, min_price: float, max_price: float,
                                price_step_size: float, volume_step_size: float):
        self.order_book_tracker._order_books[trading_pair] = CompositeOrderBook()
        bids: List[OrderBookRow] = []
        asks: List[OrderBookRow] = []
        current_price = mid_price - price_step_size / 2
        current_size = volume_step_size
        while current_price >= min_price:
            bids.append(OrderBookRow(current_price, current_size, 1))
            current_price -= price_step_size
            current_size += volume_step_size

        current_price = mid_price + price_step_size / 2
        current_size = volume_step_size
        while current_price <= max_price:
            asks.append(OrderBookRow(current_price, current_size, 1))
            current_price += price_step_size
            current_size += volume_step_size

        self.order_book_tracker._order_books[trading_pair].apply_snapshot(bids, asks, 1)
