import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.injective_v2_perpetual import injective_constants as CONSTANTS
from hummingbot.connector.exchange.injective_v2.data_sources.injective_data_source import InjectiveDataSource
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.event.events import MarketEvent, OrderBookDataSourceEvent

if TYPE_CHECKING:
    from hummingbot.connector.derivative.injective_v2_perpetual.injective_v2_perpetual_derivative import (
        InjectiveV2Dericative,
    )


class InjectiveV2PerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "InjectiveV2Dericative",
        data_source: InjectiveDataSource,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs=trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._connector = connector
        self._data_source = data_source
        self._domain = domain
        self._forwarders = []
        self._configure_event_forwarders()

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        market_id = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        funding_info = await self._data_source.funding_info(market_id=market_id)

        return funding_info

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def listen_for_subscriptions(self):
        # Subscriptions to streams is handled by the data_source
        # Here we just make sure the data_source is listening to the streams
        market_ids = [await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                      for trading_pair in self._trading_pairs]
        await self._data_source.start(market_ids=market_ids)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        snapshot = await self._data_source.perpetual_order_book_snapshot(market_id=symbol, trading_pair=trading_pair)
        return snapshot

    async def _parse_order_book_diff_message(self, raw_message: OrderBookMessage, message_queue: asyncio.Queue):
        # In Injective 'raw_message' is not a raw message, but the OrderBookMessage with type Trade created
        # by the data source
        message_queue.put_nowait(raw_message)

    async def _parse_trade_message(self, raw_message: OrderBookMessage, message_queue: asyncio.Queue):
        # In Injective 'raw_message' is not a raw message, but the OrderBookMessage with type Trade created
        # by the data source
        message_queue.put_nowait(raw_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # In Injective 'raw_message' is not a raw message, but the FundingInfoUpdate created
        # by the data source
        message_queue.put_nowait(raw_message)

    def _configure_event_forwarders(self):
        event_forwarder = EventForwarder(to_function=self._process_order_book_event)
        self._forwarders.append(event_forwarder)
        self._data_source.add_listener(
            event_tag=OrderBookDataSourceEvent.DIFF_EVENT, listener=event_forwarder
        )

        event_forwarder = EventForwarder(to_function=self._process_public_trade_event)
        self._forwarders.append(event_forwarder)
        self._data_source.add_listener(event_tag=OrderBookDataSourceEvent.TRADE_EVENT, listener=event_forwarder)

        event_forwarder = EventForwarder(to_function=self._process_funding_info_event)
        self._forwarders.append(event_forwarder)
        self._data_source.add_listener(event_tag=MarketEvent.FundingInfo, listener=event_forwarder)

    def _process_order_book_event(self, order_book_diff: OrderBookMessage):
        self._message_queue[self._diff_messages_queue_key].put_nowait(order_book_diff)

    def _process_public_trade_event(self, trade_update: OrderBookMessage):
        self._message_queue[self._trade_messages_queue_key].put_nowait(trade_update)

    def _process_funding_info_event(self, funding_info_update: FundingInfoUpdate):
        self._message_queue[self._funding_info_messages_queue_key].put_nowait(funding_info_update)
