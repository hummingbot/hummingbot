import asyncio
from typing import AsyncGenerator, Dict, List, Optional

from aiostream import stream
from bxsolana.provider import Provider
from bxsolana_trader_proto import GetOrderStatusResponse, GetOrderStatusStreamResponse, OrderStatus

from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_constants import OPENBOOK_PROJECT
from hummingbot.core.data_type.in_flight_order import OrderState


class BloxrouteOpenbookOrderStatusManager:
    def __init__(self, provider: Provider, trading_pairs: List[str], owner_address: str):
        self._provider = provider
        self._trading_pairs = trading_pairs
        self._owner_address = owner_address

        self._markets_to_order_statuses: Dict[str, Dict[int, OrderStatus]] = {}

        self._started = False
        self._is_ready = False

        self._order_status_stream_polling_task = None
        self._combined_order_status_stream = None

    @property
    def is_ready(self):
        return self._is_ready

    @property
    def started(self):
        return self._started

    def start(self):
        if not self._started:
            self._started = True

            self._initalize_order_status_stream()
            self._order_status_stream_polling_task = asyncio.create_task(self._poll_order_status_updates())
            self._is_ready = True

    async def stop(self):
        if self._order_status_stream_polling_task is not None:
            self._order_status_stream_polling_task.cancel()
            self._order_status_stream_polling_task = None

    def _initalize_order_status_stream(self):
        streams = []
        for trading_pair in self._trading_pairs:
            os_stream = self._provider.get_order_status_stream(
                market=trading_pair, owner_address=self._owner_address, project=OPENBOOK_PROJECT
            )
            streams.append(os_stream)
        self._combined_order_status_stream = stream.merge(*streams)

    async def _poll_order_status_updates(self):
        if self._combined_order_status_stream is None:
            raise Exception("order status stream was not initialized")
        async with self._combined_order_status_stream.stream() as os_stream:
            async for order_status_update in os_stream:
                self._apply_order_status_update(order_status_update.orderbook)

    def _apply_order_status_update(self, update: GetOrderStatusStreamResponse):
        normalized_trading_pair = normalize_trading_pair(update.order_info.market)
        if normalized_trading_pair not in self._markets_to_order_statuses:
            self._markets_to_order_statuses[normalized_trading_pair] = {
                update.order_info.client_order_i_d: update.order_info.order_status
            }
        else:
            order_statuses = self._markets_to_order_statuses[normalized_trading_pair]
            order_statuses.update({update.order_info.client_order_i_d: update.order_info.order_status})

    def get_order_status(self, trading_pair: str, client_order_id: int) -> OrderStatus:
        if trading_pair in self._markets_to_order_statuses:
            os_udpates = self._markets_to_order_statuses[trading_pair]
            if client_order_id in os_udpates:
                return os_udpates[client_order_id]

        return OrderStatus.OS_UNKNOWN


def normalize_trading_pair(trading_pair: str):
    trading_pair = trading_pair.replace("-", "")
    trading_pair = trading_pair.replace("/", "")
    return trading_pair
