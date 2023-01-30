import asyncio
from typing import Callable, Dict, List, Optional

from hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base import (
    GatewayCLOBAPIDataSourceBase,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.event.events import OrderBookDataSourceEvent


class GatewayCLOBSPOTAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger = None

    def __init__(self, trading_pairs: List[str], api_data_source: GatewayCLOBAPIDataSourceBase):
        super().__init__(trading_pairs=trading_pairs)
        self._api_data_source = api_data_source
        self._snapshot_receiver: Optional[Callable] = None
        self._diff_receiver: Optional[Callable] = None
        self._trade_receiver: Optional[Callable] = None

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None,
    ) -> Dict[str, float]:
        last_traded_prices = {
            trading_pair: float(await self._api_data_source.get_last_traded_price(trading_pair=trading_pair))
            for trading_pair in trading_pairs
        }
        return last_traded_prices

    def add_forwarders(self):
        self._snapshot_receiver = self._message_queue[self._snapshot_messages_queue_key].put_nowait
        self._diff_receiver = self._message_queue[self._diff_messages_queue_key].put_nowait
        self._trade_receiver = self._message_queue[self._trade_messages_queue_key].put_nowait
        self._api_data_source.add_forwarder(
            event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, receiver=self._snapshot_receiver
        )
        self._api_data_source.add_forwarder(
            event_tag=OrderBookDataSourceEvent.DIFF_EVENT, receiver=self._diff_receiver
        )
        self._api_data_source.add_forwarder(
            event_tag=OrderBookDataSourceEvent.TRADE_EVENT, receiver=self._trade_receiver
        )

    def remove_forwarders(self):
        self._api_data_source.remove_forwarder(
            event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, receiver=self._snapshot_receiver
        )
        self._api_data_source.remove_forwarder(
            event_tag=OrderBookDataSourceEvent.DIFF_EVENT, receiver=self._diff_receiver
        )
        self._api_data_source.remove_forwarder(
            event_tag=OrderBookDataSourceEvent.TRADE_EVENT, receiver=self._trade_receiver
        )

    async def listen_for_subscriptions(self):
        """Not used."""
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """Not used."""
        pass

    async def _parse_trade_message(self, raw_message: OrderBookMessage, message_queue: asyncio.Queue):
        """Injective fires two trade updates per transaction.

        Generally, CEXes publish trade updates from the perspective of the taker, so we ignore makers.
        """
        if raw_message.content["is_taker"]:
            message_queue.put_nowait(raw_message)

    async def _parse_order_book_diff_message(self, raw_message: OrderBookMessage, message_queue: asyncio.Queue):
        message_queue.put_nowait(raw_message)

    async def _parse_order_book_snapshot_message(self, raw_message: OrderBookMessage, message_queue: asyncio.Queue):
        message_queue.put_nowait(raw_message)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._api_data_source.get_order_book_snapshot(trading_pair=trading_pair)
        return snapshot
