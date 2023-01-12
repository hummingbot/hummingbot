import asyncio
from typing import Dict, List

from bxsolana.provider import Provider, WsProvider
from bxsolana_trader_proto.api import GetOrderbookResponse, OrderbookItem

from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_constants import OPENBOOK_PROJECT


class Orderbook:
    asks: List[OrderbookItem]
    bids: List[OrderbookItem]

    def __init__(self, asks: List[OrderbookItem], bids: List[OrderbookItem]):
        self.asks = asks
        self.bids = bids


class OrderbookInfo:
    best_ask_price: float = 0
    best_ask_size: float = 0
    best_bid_price: float = 0
    best_bid_size: float = 0
    latest_order_book: Orderbook

    def __init__(
        self,
        best_ask_price: float,
        best_ask_size: float,
        best_bid_price: float,
        best_bid_size: float,
        latest_order_book: Orderbook,
    ):
        self.best_ask_price = best_ask_price
        self.best_ask_size = best_ask_size
        self.best_bid_price = best_bid_price
        self.best_bid_size = best_bid_size
        self.latest_order_book = latest_order_book


class BloxrouteOpenbookOrderbookManager:
    def __init__(self, provider: Provider, trading_pairs: List[str]):
        self._provider = provider

        for index, trading_pair in enumerate(trading_pairs):
            trading_pairs[index] = normalize_trading_pair(trading_pair)

        self._trading_pairs = trading_pairs
        self._order_books: Dict[str, OrderbookInfo] = {}

        self._started = False
        self._ready = asyncio.Event()
        self._is_ready = False

        self._orderbook_polling_task = None

    async def ready(self):
        await self._ready.wait()

    @property
    def is_ready(self):
        return self._is_ready

    @property
    def started(self):
        return self._started

    async def start(self):
        if not self._started:
            self._started = True
            await self._initialize_order_books()

            self._is_ready = True
            self._orderbook_polling_task = asyncio.create_task(
                self._poll_order_book_updates()
            )

    async def stop(self):
        if self._orderbook_polling_task is not None:
            self._orderbook_polling_task.cancel()
            self._orderbook_polling_task = None

    async def _initialize_order_books(self):
        await self._provider.connect()
        for trading_pair in self._trading_pairs:
            orderbook: GetOrderbookResponse = await self._provider.get_orderbook(market=trading_pair, limit=5)
            self._apply_order_book_update(orderbook)

    async def _poll_order_book_updates(self):
        await self._provider.connect()
        order_book_stream = self._provider.get_orderbooks_stream(markets=self._trading_pairs, limit=5, project=OPENBOOK_PROJECT)
        async for order_book_update in order_book_stream:
            self._apply_order_book_update(order_book_update.orderbook)

    def _apply_order_book_update(self, update: GetOrderbookResponse):
        best_ask = update.asks[0]
        best_bid = update.bids[-1]

        normalized_trading_pair = normalize_trading_pair(update.market)

        best_ask_price = best_ask.price
        best_ask_size = best_ask.size
        best_bid_price = best_bid.price
        best_bid_size = best_bid.size
        latest_order_book = Orderbook(update.asks, update.bids)

        if normalized_trading_pair not in self._order_books:
            self._order_books[normalized_trading_pair] = OrderbookInfo(
                best_ask_price=best_ask_price,
                best_ask_size=best_ask_size,
                best_bid_price=best_bid_price,
                best_bid_size=best_bid_size,
                latest_order_book=latest_order_book,
            )
        else:
            ob_info = self._order_books[normalized_trading_pair]

            ob_info.best_ask_price = best_ask_price
            ob_info.best_ask_size = best_ask_size
            ob_info.best_bid_price = best_bid_price
            ob_info.best_bid_size = best_bid_size
            ob_info.latest_order_book = latest_order_book

    def get_order_book(self, trading_pair: str) -> Orderbook:
        normalized_trading_pair = normalize_trading_pair(trading_pair)
        return self._order_books[normalized_trading_pair].latest_order_book

    def get_price_with_opportunity_size(self, trading_pair: str, is_buy: bool) -> (float, float):
        normalized_trading_pair = normalize_trading_pair(trading_pair)
        if normalized_trading_pair not in self._order_books:
            raise Exception(f"order book manager does not support ${trading_pair}")

        ob_info = self._order_books[normalized_trading_pair]
        return (
            (ob_info.best_bid_price, ob_info.best_bid_size)
            if is_buy
            else (ob_info.best_ask_price, ob_info.best_ask_size)
        )


def normalize_trading_pair(trading_pair: str):
    trading_pair = trading_pair.replace("-", "")
    trading_pair = trading_pair.replace("/", "")
    return trading_pair
