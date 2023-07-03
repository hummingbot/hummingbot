import asyncio
from typing import Dict, List, Optional

from hummingbot.connector.gateway.clob_perp.data_sources.clob_perp_api_data_source_base import CLOBPerpAPIDataSourceBase
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.event.events import MarketEvent, OrderBookDataSourceEvent


class GatewayCLOBPerpAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger = None

    def __init__(self, trading_pairs: List[str], api_data_source: CLOBPerpAPIDataSourceBase) -> None:
        super().__init__(trading_pairs=trading_pairs)
        self._api_data_source = api_data_source

        self._forwarders: List[EventForwarder] = []

        self._add_forwarders()

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
        """Not used."""
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """Not used."""
        pass

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        return await self._api_data_source.get_funding_info(trading_pair=trading_pair)

    def _add_forwarders(self):
        event_forwarder = EventForwarder(to_function=self._message_queue[self._snapshot_messages_queue_key].put_nowait)
        self._forwarders.append(event_forwarder)
        self._api_data_source.add_listener(event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, listener=event_forwarder)

        event_forwarder = EventForwarder(to_function=self._message_queue[self._diff_messages_queue_key].put_nowait)
        self._forwarders.append(event_forwarder)
        self._api_data_source.add_listener(event_tag=OrderBookDataSourceEvent.DIFF_EVENT, listener=event_forwarder)

        event_forwarder = EventForwarder(to_function=self._message_queue[self._trade_messages_queue_key].put_nowait)
        self._forwarders.append(event_forwarder)
        self._api_data_source.add_listener(event_tag=OrderBookDataSourceEvent.TRADE_EVENT, listener=event_forwarder)

        event_forwarder = EventForwarder(
            to_function=self._message_queue[self._funding_info_messages_queue_key].put_nowait
        )
        self._forwarders.append(event_forwarder)
        self._api_data_source.add_listener(
            event_tag=MarketEvent.FundingInfo, listener=event_forwarder
        )

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

    async def _parse_funding_info_message(self, raw_message: FundingInfoUpdate, message_queue: asyncio.Queue):
        message_queue.put_nowait(raw_message)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Fetches order book snapshot for specified trading pair.
        Used by APIOrderBookDataSource
        """
        snapshot = await self._api_data_source.get_order_book_snapshot(trading_pair=trading_pair)
        return snapshot
