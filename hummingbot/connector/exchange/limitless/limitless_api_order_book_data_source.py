"""Order book data source that delegates to the inner LimitlessConnector."""

import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.limitless import limitless_constants as CONSTANTS, limitless_web_utils as web_utils
from hummingbot.connector.exchange.limitless.limitless_order_book import LimitlessOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.limitless.limitless_exchange import LimitlessExchange


class LimitlessAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "LimitlessExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None,
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """Fetch orderbook snapshot via inner connector."""
        inner = self._connector._inner_connector
        slug = self._connector._trading_pair_to_slug(trading_pair)
        ob = await inner.get_order_book(slug)
        return {
            "trading_pair": trading_pair,
            "bids": [[b["price"], b["size"]] for b in ob.get("bids", [])],
            "asks": [[a["price"], a["size"]] for a in ob.get("asks", [])],
            "time": time.time(),
        }

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._request_order_book_snapshot(trading_pair)
        timestamp = snapshot["time"]
        snapshot_msg = LimitlessOrderBook.snapshot_message_from_exchange(
            snapshot, timestamp, metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = web_utils.wss_url(self._domain)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """Subscribe to orderbook updates for all trading pairs.

        Since the inner LimitlessConnector handles WS subscriptions for the
        actual data feed, we also subscribe via the Hummingbot WS assistant
        if needed. For now, the orderbook data is primarily served by polling
        the inner connector.
        """
        try:
            for trading_pair in self._trading_pairs:
                slug = self._connector._trading_pair_to_slug(trading_pair)
                payload = {
                    "method": "subscribe",
                    "subscription": {
                        "type": "subscribe_market_prices",
                        "marketSlugs": [slug],
                    },
                }
                subscribe_request = WSJSONRequest(payload=payload)
                await ws.send(subscribe_request)
            self.logger().info("Subscribed to public order book channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book data streams."
            )
            raise

    async def _parse_order_book_diff_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        # Extract slug from message and map back to trading pair
        data = raw_message.get("data", raw_message)
        slug = data.get("marketSlug", data.get("market_slug", ""))
        trading_pair = self._connector._slug_to_trading_pair(slug)
        if not trading_pair:
            return

        ob = data.get("orderbook", data)
        bids_raw = ob.get("bids", [])
        asks_raw = ob.get("asks", [])

        msg_data = {
            "trading_pair": trading_pair,
            "bids": [[b.get("price", 0), b.get("size", 0)] for b in bids_raw],
            "asks": [[a.get("price", 0), a.get("size", 0)] for a in asks_raw],
        }
        timestamp = time.time()
        order_book_message = LimitlessOrderBook.diff_message_from_exchange(
            msg_data, timestamp, {"trading_pair": trading_pair}
        )
        message_queue.put_nowait(order_book_message)

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        """Subscribe to orderbook updates for a single trading pair."""
        try:
            if trading_pair not in self._trading_pairs:
                self._trading_pairs.append(trading_pair)
            self.logger().info(f"Subscribed to {trading_pair}")
            return True
        except Exception:
            self.logger().error(f"Failed to subscribe to {trading_pair}")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        """Unsubscribe from orderbook updates for a single trading pair."""
        try:
            if trading_pair in self._trading_pairs:
                self._trading_pairs.remove(trading_pair)
            self.logger().info(f"Unsubscribed from {trading_pair}")
            return True
        except Exception:
            self.logger().error(f"Failed to unsubscribe from {trading_pair}")
            return False

    async def _parse_trade_message(
        self, raw_message: Dict[str, Any], message_queue: asyncio.Queue
    ):
        pass

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message:
            event_type = event_message.get("channel", event_message.get("type", ""))
            if "orderbook" in event_type.lower() or "l2book" in event_type.lower():
                channel = self._diff_messages_queue_key
            elif "trade" in event_type.lower():
                channel = self._trade_messages_queue_key
        return channel
