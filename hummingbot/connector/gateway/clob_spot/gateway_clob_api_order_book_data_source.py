import asyncio
import logging
from typing import Dict, List, Optional

from hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base import (
    GatewayCLOBAPIDataSourceBase,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.event.events import OrderBookDataSourceEvent
from hummingbot.logger import HummingbotLogger


class GatewayCLOBSPOTAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _gcsaobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._gcsaobds_logger is None:
            cls._gcsaobds_logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._gcsaobds_logger

    def __init__(self, trading_pairs: List[str], api_data_source: GatewayCLOBAPIDataSourceBase):
        super().__init__(trading_pairs=trading_pairs)
        self._api_data_source = api_data_source

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

    async def listen_for_subscriptions(self):
        await self._api_data_source.start()

        snapshot_receiver = self._message_queue[self._snapshot_messages_queue_key].put_nowait
        trade_receiver = self._message_queue[self._trade_messages_queue_key].put_nowait
        self._api_data_source.add_forwarder(event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, receiver=snapshot_receiver)
        self._api_data_source.add_forwarder(event_tag=OrderBookDataSourceEvent.TRADE_EVENT, receiver=trade_receiver)

        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise
        finally:
            self._api_data_source.remove_forwarder(
                event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, receiver=snapshot_receiver
            )
            self._api_data_source.remove_forwarder(event_tag=OrderBookDataSourceEvent.TRADE_EVENT, receiver=trade_receiver)
            await self._api_data_source.stop()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """No diffs provided by the Injective API."""
        pass

    async def _parse_trade_message(self, raw_message: OrderBookMessage, message_queue: asyncio.Queue):
        """Injective fires two trade updates per transaction.

        Generally, CEXes publish trade updates from the perspective of the taker, so we ignore makers.
        """
        if raw_message.content["is_taker"]:
            message_queue.put_nowait(raw_message)

    async def _parse_order_book_snapshot_message(self, raw_message: OrderBookMessage, message_queue: asyncio.Queue):
        message_queue.put_nowait(raw_message)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._api_data_source.get_order_book_snapshot(trading_pair=trading_pair)
        return snapshot
