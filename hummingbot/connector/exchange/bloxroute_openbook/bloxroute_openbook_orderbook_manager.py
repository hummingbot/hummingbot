import asyncio
from asyncio import Task
from time import time
from typing import Dict, List, Optional

from bxsolana.provider import Provider
from bxsolana_trader_proto.api import GetOrderbookResponse, GetOrderStatusStreamResponse, OrderbookItem, OrderStatus

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


class OrderStatusInfo:
    order_status: OrderStatus
    timestamp: float

    def __init__(self, order_status: OrderStatus, timestamp: float):
        self.order_status = order_status
        self.timestamp = timestamp


class BloxrouteOpenbookOrderManager:
    def __init__(self, provider: Provider, trading_pairs: List[str], owner_address: str):
        self._provider = provider
        self._owner_address = owner_address

        for index, trading_pair in enumerate(trading_pairs):
            trading_pairs[index] = normalize_trading_pair(trading_pair)
        self._trading_pairs = trading_pairs

        self._order_books: Dict[str, OrderbookInfo] = {}
        self._markets_to_order_statuses: Dict[str, Dict[int, OrderStatusInfo]] = {}

        self._started = False
        self._ready = asyncio.Event()
        self._is_ready = False

        self._orderbook_polling_task: Optional[Task] = None
        self._order_status_running_tasks: List[Task] = []
        self._order_status_polling_task: Optional[Task] = None

        self._order_status_updates = asyncio.Queue()

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
            self._orderbook_polling_task = asyncio.create_task(self._poll_order_book_updates())

            await self._initialize_order_status_streams()
            self._order_status_polling_task = asyncio.create_task(self._poll_order_status_updates())

            await asyncio.sleep(5)

            self._is_ready = True

    async def stop(self):
        await self._provider.close()
        if self._orderbook_polling_task is not None:
            self._orderbook_polling_task.cancel()
            self._orderbook_polling_task = None
        for task in self._order_status_running_tasks:
            if task is not None:
                task.cancel()
        self._order_status_running_tasks.clear()
        if self._order_status_polling_task is not None:
            self._order_status_polling_task.cancel()
            self._order_status_polling_task = None

    async def _initialize_order_books(self):
        await self._provider.connect()
        for trading_pair in self._trading_pairs:
            orderbook = await self._provider.get_orderbook(market=trading_pair, limit=5, project=OPENBOOK_PROJECT)
            self._apply_order_book_update(orderbook)

    async def _initialize_order_status_streams(self):
        for trading_pair in self._trading_pairs:
            normalized_trading_pair = normalize_trading_pair(trading_pair)
            self._markets_to_order_statuses.update({normalized_trading_pair: {}})

            initialize_order_stream_task = asyncio.create_task(self._initialize_order_status_stream(trading_pair=trading_pair))
            self._order_status_running_tasks.append(initialize_order_stream_task)

    async def _initialize_order_status_stream(self, trading_pair: str):
        await self._provider.connect()
        order_status_stream = self._provider.get_order_status_stream(
            market=trading_pair, owner_address=self._owner_address, project=OPENBOOK_PROJECT
        )

        first_response = await order_status_stream.__anext__()
        self._order_status_updates.put_nowait(first_response)
        async for order_status_update in order_status_stream:
            self._order_status_updates.put_nowait(order_status_update)

    async def _poll_order_book_updates(self):
        await self._provider.connect()
        order_book_stream = self._provider.get_orderbooks_stream(
            markets=self._trading_pairs, limit=5, project=OPENBOOK_PROJECT
        )
        async for order_book_update in order_book_stream:
            self._apply_order_book_update(order_book_update.orderbook)

    async def _poll_order_status_updates(self):
        while True:
            os_update: GetOrderStatusStreamResponse = await self._order_status_updates.get()

            market = os_update.order_info.market
            client_order_i_d = os_update.order_info.client_order_i_d
            order_status = os_update.order_info.order_status

            self._apply_order_status_update(market, client_order_i_d, order_status)

    def _apply_order_book_update(self, update: GetOrderbookResponse):
        normalized_trading_pair = normalize_trading_pair(update.market)

        best_ask = update.asks[0] if update.asks else OrderbookItem(price=0, size=0)
        best_bid = update.bids[-1] if update.bids else OrderbookItem(price=0, size=0)

        best_ask_price = best_ask.price
        best_ask_size = best_ask.size
        best_bid_price = best_bid.price
        best_bid_size = best_bid.size

        latest_order_book = Orderbook(update.asks, update.bids)

        self._order_books.update(
            {
                normalized_trading_pair: OrderbookInfo(
                    best_ask_price=best_ask_price,
                    best_ask_size=best_ask_size,
                    best_bid_price=best_bid_price,
                    best_bid_size=best_bid_size,
                    latest_order_book=latest_order_book,
                )
            }
        )

    def _apply_order_status_update(self, market: str, client_order_i_d: int, order_status: OrderStatus):
        normalized_trading_pair = normalize_trading_pair(market)
        if normalized_trading_pair not in self._markets_to_order_statuses:
            raise Exception(f"order manager does not support updates for ${normalized_trading_pair}")

        order_statuses = self._markets_to_order_statuses[normalized_trading_pair]
        order_statuses.update({client_order_i_d: OrderStatusInfo(order_status=order_status, timestamp=time())})

    def get_order_book(self, trading_pair: str) -> Orderbook:
        normalized_trading_pair = normalize_trading_pair(trading_pair)
        if normalized_trading_pair not in self._order_books:
            raise Exception(f"order book manager does not support ${trading_pair}")

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

    def get_order_status(self, trading_pair: str, client_order_id: int) -> OrderStatusInfo:
        normalized_trading_pair = normalize_trading_pair(trading_pair)
        if normalized_trading_pair not in self._markets_to_order_statuses:
            raise Exception(f"order book manager does not support ${trading_pair}")

        order_statuses = self._markets_to_order_statuses[normalized_trading_pair]
        if client_order_id in order_statuses:
            return order_statuses[client_order_id]

        return OrderStatusInfo(OrderStatus.OS_UNKNOWN, time())


def normalize_trading_pair(trading_pair: str):
    trading_pair = trading_pair.replace("-", "")
    trading_pair = trading_pair.replace("/", "")
    return trading_pair
