import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from gql import Client
from gql.transport.appsync_websockets import AppSyncWebsocketsTransport

from hummingbot.connector.exchange.polkadex import polkadex_constants as CONSTANTS
from hummingbot.connector.exchange.polkadex.graphql.general.streams import websocket_streams_session_provided
from hummingbot.connector.exchange.polkadex.graphql.market.market import get_orderbook
from hummingbot.connector.exchange.polkadex.polkadex_order_book import PolkadexOrderbook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.polkadex.polkadex_exchange import PolkadexExchange


class PolkadexOrderbookDataSource(OrderBookTrackerDataSource):
    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'PolkadexExchange',
                 api_factory: WebAssistantsFactory,
                 api_key: str):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._api_factory = api_factory
        self._api_key = api_key

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _parse_trade_message(self, raw_message: Dict[str,Any],
                                   message_queue: asyncio.Queue):
        print("Raw message from trade subciption")
        for msg in raw_message["websocket_streams"]["data"]:
            trade_message = PolkadexOrderbook.trade_message_from_exchange(msg)
            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Dict[str, List[Dict[str, str]]]],
                                             message_queue: asyncio.Queue):
        """
               {
                   'websocket_streams': {
                       'data': '[{"side":"Ask","price":5554500000000,"qty":7999200000000 ,"seq":20}]'
                   }
               }
        """
        diff_message = PolkadexOrderbook.diff_message_from_exchange(raw_message)
        message_queue.put_nowait(diff_message)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        print("Getting orderbook snapshot for: ", trading_pair)
        result: List[Dict[str, Any]] = await get_orderbook(trading_pair, None, None, self._connector.endpoint,
                                                           self._api_key)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = PolkadexOrderbook.snapshot_message_from_exchange(
            result,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    def on_recent_trade_callback(self, message, trading_pair):
        print("Recent trade: ", message)
        message["market"] = trading_pair
        self._message_queue[self._trade_messages_queue_key].put_nowait(message)

    def on_ob_increment(self, message, trading_pair):
        print("ob inc: ", message)
        message["market"] = trading_pair
        self._message_queue[self._diff_messages_queue_key].put_nowait(message)

    async def listen_for_subscriptions(self):
        transport = AppSyncWebsocketsTransport(url=self._connector.endpoint, auth=self._connector.auth)
        tasks = []
        async with Client(transport=transport, fetch_schema_from_transport=False) as session:
            for trading_pair in self._trading_pairs:
                tasks.append(
                    asyncio.create_task(
                        websocket_streams_session_provided(trading_pair + "-recent-trades", session,
                                                           self.on_recent_trade_callback, trading_pair)))
                tasks.append(
                    asyncio.create_task(
                        websocket_streams_session_provided(trading_pair + "-ob-inc", session,
                                                           self.on_ob_increment, trading_pair)))
                await asyncio.wait(tasks)

    async def _subscribe_channels(self, ws: WSAssistant):
        pass

    async def _connected_websocket_assistant(self) -> WSAssistant:
        return await self._api_factory.get_ws_assistant()

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        self.logger().error(
            "Trying to filter the message based on channel... :", event_message,
            exc_info=True
        )
        raise NotImplementedError
