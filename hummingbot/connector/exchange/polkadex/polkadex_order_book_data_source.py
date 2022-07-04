import asyncio
import time
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from gql import Client
from gql.transport.appsync_auth import AppSyncApiKeyAuthentication
from gql.transport.appsync_websockets import AppSyncWebsocketsTransport
from market.market import get_recent_trades

from hummingbot.connector.exchange.polkadex.graphql.general.streams import websocket_streams_session_provided
from hummingbot.connector.exchange.polkadex.graphql.market.market import get_orderbook
from hummingbot.connector.exchange.polkadex.polkadex_order_book import PolkadexOrderbook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class PolkadexOrderbookDataSource(OrderBookTrackerDataSource):
    def __init__(self, trading_pairs: List[str], endpoint, api_key):
        self.host = str(urlparse(endpoint).netloc)
        self.auth = AppSyncApiKeyAuthentication(host=self.host, api_key=api_key)

        self.transport = AppSyncWebsocketsTransport(url=endpoint, auth=self.auth)
        super().__init__(trading_pairs)

    async def trade_callback(self, message):
        print("recvd trade: ", message)
        self._message_queue[self._trade_messages_queue_key].put_nowait(message)

    async def ob_inc_callback(self, message):
        print("recvd ob_inc: ", message)
        self._message_queue[self._diff_messages_queue_key].put_nowait(message)

    async def subscribe_polkadex_trades_and_ob_inc(self):
        tasks = []
        async with Client(transport=self.transport, fetch_schema_from_transport=False) as session:
            for market in self._trading_pairs:
                tasks.append(asyncio.create_task(websocket_streams_session_provided(market + "-raw-trade",
                                                                                    session,
                                                                                    self.trade_callback)))
                tasks.append(asyncio.create_task(websocket_streams_session_provided(market + "-ob-inc",
                                                                                    session,
                                                                                    self.ob_inc_callback)))
            await asyncio.wait(tasks)

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        results_dict = {}
        for market in trading_pairs:
            result = await get_recent_trades(market, 1, None)
            results_dict[market] = float(result["items"][0]["p"])
        return results_dict

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trade_message = PolkadexOrderbook.trade_message_from_exchange(raw_message)
        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        diff_message = PolkadexOrderbook.diff_message_from_exchange(raw_message)
        message_queue.put_nowait(diff_message)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        result = await get_orderbook(trading_pair, None, None)
        snapshot_timestamp: float = time.time()
        return PolkadexOrderbook.snapshot_message_from_exchange(result, snapshot_timestamp,
                                                                metadata={"trading_pair": trading_pair})

    async def _connected_websocket_assistant(self) -> WSAssistant:
        pass

    async def _subscribe_channels(self, ws: WSAssistant):
        await self.subscribe_polkadex_trades_and_ob_inc()

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        pass
