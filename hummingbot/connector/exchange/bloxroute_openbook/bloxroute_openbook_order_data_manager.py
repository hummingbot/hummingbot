import asyncio
import time
from asyncio import Task
from typing import Dict, List, Optional

import bxsolana_trader_proto.api as api

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_constants import (
    HUMMINGBOT_LOG_DECIMALS,
    ORDERBOOK_LIMIT,
    SPOT_ORDERBOOK_PROJECT,
)
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_book import (
    Orderbook,
    OrderbookInfo,
    OrderStatusInfo,
)
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_provider import BloxrouteOpenbookProvider


class BloxrouteOpenbookOrderDataManager:
    def __init__(self, provider: BloxrouteOpenbookProvider, trading_pairs: List[str], owner_address: str):
        self._provider = provider
        self._owner_address = owner_address

        self._trading_pairs = []
        for trading_pair in trading_pairs:
            self._trading_pairs.append(normalize_trading_pair(trading_pair))

        self._order_books: Dict[str, OrderbookInfo] = {}
        self._markets_to_order_statuses: Dict[str, Dict[int, List[OrderStatusInfo]]] = {}

        self._start_lock = asyncio.Lock()
        self._started = asyncio.Event()
        self._ready = asyncio.Event()

        self._orderbook_polling_task: Optional[Task] = None
        self._order_status_running_tasks: List[Task] = []
        self._order_status_polling_task: Optional[Task] = None

    async def ready(self):
        await self._ready.wait()

    @property
    def is_ready(self):
        return self._ready.is_set()

    async def start(self):
        if not self._started.is_set():
            self._started.set()

            await self._initialize_order_books()
            self._orderbook_polling_task = asyncio.create_task(self._poll_order_book_updates())

            await self._initialize_order_status_streams()

            self._ready.set()

    async def stop(self):
        if self._orderbook_polling_task is not None:
            self._orderbook_polling_task.cancel()
            self._orderbook_polling_task = None
        for task in self._order_status_running_tasks:
            if task is not None:
                task.cancel()
        self._order_status_running_tasks.clear()

    async def _initialize_order_books(self):
        await self._provider.wait_connect()
        for trading_pair in self._trading_pairs:
            blxr_orderbook = await self._provider.get_orderbook(
                market=trading_pair, limit=ORDERBOOK_LIMIT, project=SPOT_ORDERBOOK_PROJECT
            )

            self._apply_order_book_update(blxr_orderbook)

    async def _initialize_order_status_streams(self):
        await self._provider.wait_connect()
        for trading_pair in self._trading_pairs:
            self._markets_to_order_statuses.update({trading_pair: {}})

            initialize_order_stream_task = asyncio.create_task(
                self._poll_order_status_updates(trading_pair=trading_pair)
            )
            self._order_status_running_tasks.append(initialize_order_stream_task)

    async def _poll_order_book_updates(self):
        await self._provider.wait_connect()
        order_book_stream = self._provider.get_orderbooks_stream(
            markets=self._trading_pairs, limit=ORDERBOOK_LIMIT, project=SPOT_ORDERBOOK_PROJECT
        )

        async for order_book_update in order_book_stream:
            self._apply_order_book_update(order_book_update.orderbook)

    async def _poll_order_status_updates(self, trading_pair: str):
        await self._provider.wait_connect()
        order_status_stream = self._provider.get_order_status_stream(
            market=trading_pair, owner_address=self._owner_address, project=SPOT_ORDERBOOK_PROJECT
        )

        async for order_status_update in order_status_stream:
            self._apply_order_status_update(order_status_update.order_info)

    def _apply_order_book_update(self, update: api.GetOrderbookResponse):
        normalized_trading_pair = normalize_trading_pair(update.market)

        best_ask = update.asks[0] if update.asks else api.OrderbookItem(price=0, size=0)
        best_bid = update.bids[-1] if update.bids else api.OrderbookItem(price=0, size=0)

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
                    timestamp=time.time(),
                )
            }
        )

    def _apply_order_status_update(self, os_update: api.GetOrderStatusResponse):
        normalized_trading_pair = normalize_trading_pair(os_update.market)
        if normalized_trading_pair not in self._markets_to_order_statuses:
            raise Exception(f"order manager does not support updates for ${normalized_trading_pair}")

        order_statuses = self._markets_to_order_statuses[normalized_trading_pair]
        client_order_id = os_update.client_order_i_d
        order_status_info = OrderStatusInfo(
            order_status=os_update.order_status,
            quantity_released=os_update.quantity_released,
            quantity_remaining=os_update.quantity_remaining,
            side=os_update.side,
            fill_price=os_update.fill_price,
            order_price=os_update.order_price,
            client_order_i_d=client_order_id,
            timestamp=time.time(),
        )

        updated = False
        if client_order_id in order_statuses:
            if order_statuses[client_order_id][-1].quantity_remaining != os_update.quantity_remaining:
                order_statuses[client_order_id].append(order_status_info)
                updated = True
        else:
            order_statuses[client_order_id] = [order_status_info]
            updated = True

        if updated:
            log_hummingbot(client_order_id, order_status_info)

    def get_order_book(self, trading_pair: str) -> (Orderbook, float):
        normalized_trading_pair = normalize_trading_pair(trading_pair)
        if normalized_trading_pair not in self._order_books:
            raise Exception(f"order book manager does not support ${trading_pair}")

        ob_info = self._order_books[normalized_trading_pair]
        return ob_info.latest_order_book, ob_info.timestamp

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

    def get_order_statuses(self, trading_pair: str, client_order_id: int) -> List[OrderStatusInfo]:
        normalized_trading_pair = normalize_trading_pair(trading_pair)
        if normalized_trading_pair not in self._markets_to_order_statuses:
            raise Exception(f"order book manager does not support ${trading_pair}")

        order_statuses = self._markets_to_order_statuses[normalized_trading_pair]
        if client_order_id in order_statuses:
            return order_statuses[client_order_id]

        return []


# supporting both Hummingbot and BloXroute trading pair formats
def normalize_trading_pair(trading_pair: str):
    trading_pair = trading_pair.replace("-", "")
    trading_pair = trading_pair.replace("/", "")
    return trading_pair


# logs the order info to the Hummingbot UI
def log_hummingbot(client_order_id, order_status_info):
    remaining = order_status_info.quantity_remaining
    released = order_status_info.quantity_released
    if order_status_info.side == api.Side.S_BID:
        remaining = round(remaining / order_status_info.order_price, HUMMINGBOT_LOG_DECIMALS)
        released = round(released / order_status_info.order_price, HUMMINGBOT_LOG_DECIMALS)
    HummingbotApplication.main_application().notify(
        f"order type {order_status_info.order_status.name} | quantity released: {released} | "
        f"quantity remaining: {remaining} | price:  {order_status_info.order_price} | "
        f"side: {order_status_info.side.name} | id {client_order_id}"
    )
