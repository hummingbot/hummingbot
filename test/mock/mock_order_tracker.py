from typing import List, Dict
import asyncio
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker, OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book import OrderBook


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
    def __init__(self):
        self._data_source: MockOrderBookTrackerDataSource = MockOrderBookTrackerDataSource([])
        # self._trading_pairs: List[str] = trading_pairs
        self._order_books: Dict[str, OrderBook] = {}

    # def exchange_name(self):
    #     return "MockPaperExchange" # self.__class__.__name__

    @property
    def ready(self) -> bool:
        return True

    def start(self):
        pass

    def stop(self):
        pass
