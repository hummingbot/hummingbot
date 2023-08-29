import asyncio
from typing import TYPE_CHECKING, Dict, List, Optional

from hummingbot.connector.exchange.injective_v2 import injective_constants as CONSTANTS
from hummingbot.connector.exchange.injective_v2.data_sources.injective_data_source import InjectiveDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.event.events import OrderBookDataSourceEvent

if TYPE_CHECKING:
    from hummingbot.connector.exchange.injective_v2.injective_v2_exchange import InjectiveV2Exchange


class InjectiveV2APIOrderBookDataSource(OrderBookTrackerDataSource):

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "InjectiveV2Exchange",
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
        snapshot = await self._data_source.spot_order_book_snapshot(market_id=symbol, trading_pair=trading_pair)
        return snapshot

    async def _parse_order_book_diff_message(self, raw_message: OrderBookMessage, message_queue: asyncio.Queue):
        # In Injective 'raw_message' is not a raw message, but the OrderBookMessage with type Trade created
        # by the data source
        message_queue.put_nowait(raw_message)

    async def _parse_trade_message(self, raw_message: OrderBookMessage, message_queue: asyncio.Queue):
        # In Injective 'raw_message' is not a raw message, but the OrderBookMessage with type Trade created
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

    def _process_order_book_event(self, order_book_diff: OrderBookMessage):
        self._message_queue[self._diff_messages_queue_key].put_nowait(order_book_diff)

    def _process_public_trade_event(self, trade_update: OrderBookMessage):
        self._message_queue[self._trade_messages_queue_key].put_nowait(trade_update)
