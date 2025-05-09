import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

# from bidict import bidict
from hummingbot.connector.exchange.hyperliquid import (
    hyperliquid_constants as CONSTANTS,
    hyperliquid_web_utils as web_utils,
)
from hummingbot.connector.exchange.hyperliquid.hyperliquid_order_book import HyperliquidOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.hyperliquid.hyperliquid_exchange import HyperliquidExchange


class HyperliquidAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'HyperliquidExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {
            "type": 'l2Book',
            "coin": ex_trading_pair
        }

        data = await self._connector._api_post(
            path_url=CONSTANTS.SNAPSHOT_REST_URL,
            data=params)
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot.update({"trading_pair": trading_pair})
        snapshot_timestamp: float = snapshot['time']
        snapshot_msg: OrderBookMessage = HyperliquidOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = f"{web_utils.wss_url(self._domain)}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                trades_payload = {
                    "method": "subscribe",
                    "subscription": {
                        "type": CONSTANTS.TRADES_ENDPOINT_NAME,
                        "coin": symbol,
                    }
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)

                order_book_payload = {
                    "method": "subscribe",
                    "subscription": {
                        "type": CONSTANTS.DEPTH_ENDPOINT_NAME,
                        "coin": symbol,
                    }
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=order_book_payload)

                await ws.send(subscribe_trade_request)
                await ws.send(subscribe_orderbook_request)

                self.logger().info("Subscribed to public order book, trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to order book data streams.")
            raise

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        timestamp: float = raw_message["data"]["time"] * 1e-3
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            raw_message["data"]["coin"])
        data = raw_message["data"]
        order_book_message: OrderBookMessage = HyperliquidOrderBook.diff_message_from_exchange(
            data, timestamp, {"trading_pair": trading_pair})
        message_queue.put_nowait(order_book_message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            raw_message["data"]["coin"])
        data = raw_message["data"]
        timestamp: float = raw_message["data"]["time"] * 1e-3
        trade_message: OrderBookMessage = HyperliquidOrderBook.snapshot_message_from_exchange(
            data, timestamp, {"trading_pair": trading_pair},)
        message_queue.put_nowait(trade_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message["data"]
        for trade_data in data:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                trade_data["coin"])
            trade_message: OrderBookMessage = HyperliquidOrderBook.trade_message_from_exchange(
                trade_data, {"trading_pair": trading_pair})
            message_queue.put_nowait(trade_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message:
            stream_name = event_message.get("channel")
            if "l2Book" in stream_name:
                channel = self._diff_messages_queue_key
            elif "trades" in stream_name:
                channel = self._trade_messages_queue_key
        return channel
