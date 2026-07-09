import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.decibel_perpetual import (
    decibel_perpetual_constants as CONSTANTS,
    decibel_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
        DecibelPerpetualDerivative,
    )


class DecibelPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "DecibelPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._ping_task: Optional[asyncio.Task] = None
        # Map market addresses to trading pairs for WebSocket message routing
        self._market_addr_to_trading_pair: Dict[str, str] = {}

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        """
        Get last traded prices for given trading pairs.
        """
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    def _get_headers(self) -> Dict[str, str]:
        """
        Build headers for REST requests.
        Includes API key if available for better rate limits.
        """
        headers = {}
        if hasattr(self._connector, 'api_key') and self._connector.api_key:
            headers["Authorization"] = f"Bearer {self._connector.api_key}"
        return headers

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Return an empty initial snapshot — Decibel does not expose a REST
        orderbook/depth endpoint, so the book is populated entirely via the
        WebSocket "depth:<market_addr>" channel (see _subscribe_channels).
        The first WS message delivered for the subscribed pair is a full
        snapshot, after which diffs (if any) are applied to the same book.

        Also pre-populate the market_addr mapping so incoming WS messages can
        be routed back to the trading pair.
        """
        try:
            market_addr = await self._connector.get_market_addr_for_pair(trading_pair)
            self._market_addr_to_trading_pair[market_addr] = trading_pair
            self.logger().debug(f"Mapped market address {market_addr[:16]}... to {trading_pair}")
        except Exception:
            self.logger().exception(f"Failed to pre-populate market addr mapping for {trading_pair}")

        timestamp = time.time()
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": int(timestamp * 1000),
                "bids": [],
                "asks": []
            },
            timestamp=timestamp
        )

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        """
        Get funding rate information for a trading pair from the /prices endpoint.
        """
        rest_assistant = await self._api_factory.get_rest_assistant()
        market_addr = await self._connector.get_market_addr_for_pair(trading_pair)

        current_time = int(time.time())
        next_funding_time = ((current_time // 3600) + 1) * 3600

        try:
            response = await rest_assistant.execute_request(
                url=web_utils.public_rest_url(path_url=CONSTANTS.GET_MARKET_PRICES_PATH_URL, domain=self._domain),
                params={"market": market_addr},
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.GET_MARKET_PRICES_PATH_URL,
                headers=self._get_headers()
            )
            price_data = response[0] if isinstance(response, list) and len(response) > 0 else response

            # Decibel reports funding rate in bps or raw unit.
            # We use what's returned by the /prices endpoint.
            funding_rate_bps = Decimal(str(price_data.get("funding_rate_bps", 0)))
            funding_rate = funding_rate_bps / Decimal("10000")

            mark_price = Decimal(str(price_data.get("mark_px", 0)))
            index_price = Decimal(str(price_data.get("oracle_px", 0)))

            return FundingInfo(
                trading_pair=trading_pair,
                index_price=index_price,
                mark_price=mark_price,
                next_funding_utc_timestamp=next_funding_time,
                rate=funding_rate,
            )
        except Exception as e:
            self.logger().error(f"Failed to fetch funding info for {trading_pair}: {e}")
            raise e

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Create and connect WebSocket assistant.
        Includes API key authentication in headers.

        NOTE: We pass ping_timeout=None to disable aiohttp's protocol-level heartbeat.
        The Decibel server does not respond to raw WebSocket PING frames, which would
        cause aiohttp to close the connection with code 1006 after ping_timeout seconds.
        Instead, we send application-level {"method": "ping"} messages via _ping_task.
        """
        ws_url = web_utils.wss_url(domain=self._domain)
        ws_assistant = await self._api_factory.get_ws_assistant()

        # Add authentication headers for WebSocket connection
        headers = {}
        if hasattr(self._connector, 'api_key') and self._connector.api_key:
            headers["Authorization"] = f"Bearer {self._connector.api_key}"

        await ws_assistant.connect(
            ws_url=ws_url,
            ping_timeout=None,  # Disable aiohttp heartbeat - use app-level ping instead
            ws_headers=headers
        )

        # Start application-level ping to keep connection alive
        self._ping_task = safe_ensure_future(self._ping_websocket(ws_assistant))

        return ws_assistant

    async def _subscribe_channels(self, ws_assistant: WSAssistant):
        """
        Subscribe to public WebSocket channels.

        Decibel WebSocket topics use market addresses, not market names.
        Format: "depth:0x161b7b3f58327d057ee5824de0c1a4fc4fa3d121b847c138e921a255768a0dca"  # noqa: documentation
        """
        try:
            for trading_pair in self._trading_pairs:
                market_addr = await self._connector.get_market_addr_for_pair(trading_pair)

                # Store mapping for WebSocket message routing
                self._market_addr_to_trading_pair[market_addr] = trading_pair

                # Subscribe to order book updates
                subscribe_orderbook_request = WSJSONRequest({
                    "method": "subscribe",
                    "topic": f"{CONSTANTS.WS_MARKET_DEPTH_CHANNEL}:{market_addr}:1"
                })
                await ws_assistant.send(subscribe_orderbook_request)

                # Subscribe to trades
                subscribe_trades_request = WSJSONRequest({
                    "method": "subscribe",
                    "topic": f"{CONSTANTS.WS_MARKET_TRADES_CHANNEL}:{market_addr}"
                })
                await ws_assistant.send(subscribe_trades_request)

                # Subscribe to prices (for funding rate updates)
                subscribe_prices_request = WSJSONRequest({
                    "method": "subscribe",
                    "topic": f"{CONSTANTS.WS_MARKET_PRICE_CHANNEL}:{market_addr}"
                })
                await ws_assistant.send(subscribe_prices_request)

            self.logger().debug("Subscribed to all public channels")

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book data streams.")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        """
        Route incoming messages to the correct queue based on the topic.
        """
        topic = event_message.get("topic", "")
        self.logger().debug(f"WS message routing - topic: '{topic}', keys: {list(event_message.keys())}")
        if CONSTANTS.WS_MARKET_DEPTH_CHANNEL in topic:
            return self._snapshot_messages_queue_key
        if CONSTANTS.WS_MARKET_TRADES_CHANNEL in topic:
            return self._trade_messages_queue_key
        if CONSTANTS.WS_MARKET_PRICE_CHANNEL in topic:
            return self._funding_info_messages_queue_key
        self.logger().debug(f"WS message not routed. Full message (truncated): {str(event_message)[:500]}")
        return ""

    async def _process_message_for_unknown_channel(
        self, event_message: Dict[str, Any], websocket_assistant: WSAssistant
    ):
        """Log unrouted messages for debugging."""
        self.logger().debug(f"Unknown channel message: {str(event_message)[:300]}")

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Process order book update message.
        """
        self.logger().debug(f"Received raw orderbook message: {raw_message}")
        topic = raw_message.get("topic", "")
        # topic is "depth:{addr}" or "depth:{addr}:{level}" — addr is always index 1
        parts = topic.split(":")
        market_addr = parts[1] if len(parts) >= 2 else ""

        trading_pair = self._market_addr_to_trading_pair.get(market_addr)
        if not trading_pair:
            self.logger().warning(f"Unknown market address in orderbook message: {market_addr} from topic {topic}. Known mappings: {self._market_addr_to_trading_pair}")
            return

        # MarketDepthMessage from Decibel doesn't contain a timestamp, use current time
        timestamp = time.time()

        def _parse_level(entry) -> tuple:
            """Accept both dict {price, size} and list [price, size] formats."""
            if isinstance(entry, dict):
                return (str(entry.get("price", "0")), str(entry.get("size", "0")))
            return (str(entry[0]), str(entry[1]))

        order_book_message = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": int(timestamp * 1000),
                "bids": [_parse_level(b) for b in raw_message.get("bids", [])],
                "asks": [_parse_level(a) for a in raw_message.get("asks", [])]
            },
            timestamp=timestamp
        )

        self.logger().debug(f"Created OrderBookMessage for {trading_pair} with {len(order_book_message.bids)} bids and {len(order_book_message.asks)} asks.")
        message_queue.put_nowait(order_book_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Process trade message.
        Topic format: "trades:{marketAddr}"
        Actual message format (top-level, no 'data' wrapper):
        {
          "topic": "trades:0x3752...",
          "trades": [{"trade_id": 123, "price": 50100, "size": 0.8, ...}, ...]
        }
        """
        topic = raw_message.get("topic", "")
        parts = topic.split(":")
        market_addr = parts[1] if len(parts) >= 2 else ""

        trading_pair = self._market_addr_to_trading_pair.get(market_addr)
        if not trading_pair:
            self.logger().warning(f"Unknown market address in trade message: {market_addr}")
            return

        # trades are at the top level, not nested under 'data'
        # The docs show is_buy is not in the trade — determine from action field
        for trade in raw_message.get("trades", []):
            action = trade.get("action", "").lower()
            is_buy = "long" in action or trade.get("is_buy", False)
            ts_ms = trade.get("unix_ms", time.time() * 1000)
            trade_message = OrderBookMessage(
                OrderBookMessageType.TRADE,
                {
                    "trading_pair": trading_pair,
                    "trade_type": TradeType.BUY.value if is_buy else TradeType.SELL.value,
                    "trade_id": trade.get("trade_id"),
                    "update_id": ts_ms,
                    "price": str(trade.get("price")),
                    "amount": str(trade.get("size"))
                },
                timestamp=ts_ms / 1000
            )
            message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Process funding rate update message.
        Topic format: "market_price:{marketAddr}"
        Actual message format (top-level, no 'data' wrapper):
        {
          "topic": "market_price:0x3752...",
          "price": {"funding_rate_bps": 5, "mark_px": 50120.5, ...}
        }
        """
        topic = raw_message.get("topic", "")
        parts = topic.split(":")
        market_addr = parts[1] if len(parts) >= 2 else ""

        trading_pair = self._market_addr_to_trading_pair.get(market_addr)
        if not trading_pair:
            self.logger().warning(f"Unknown market address in funding message: {market_addr}")
            return

        # price data is under "price" key (per AsyncAPI spec)
        price_data = raw_message.get("price", raw_message)  # fallback to top-level if no 'price' key
        funding_rate_bps = price_data.get("funding_rate_bps", 0)
        funding_rate = Decimal(str(funding_rate_bps)) / Decimal("10000")

        funding_info = FundingInfoUpdate(trading_pair=trading_pair, rate=funding_rate)
        message_queue.put_nowait(funding_info)

    async def _ping_websocket(self, ws_assistant: WSAssistant):
        """
        Send periodic application-level ping to keep WebSocket connection alive.
        Decibel expects {"method": "ping"} — not raw WebSocket PING frames.
        Updates last_recv_time immediately so the connector shows as ready.
        """
        while True:
            try:
                ping_request = WSJSONRequest({"method": "ping"})
                await ws_assistant.send(ping_request)

                # Update last_recv_time directly so Hummingbot knows the connection
                # is alive even if testnet has no orderbook activity.
                self._last_recv_time = time.time()

                await asyncio.sleep(CONSTANTS.WS_PING_INTERVAL)
            except asyncio.CancelledError:
                break
            except RuntimeError as e:
                if "WS is not connected" in str(e):
                    return
                self.logger().exception("Unexpected error while sending ping")
                break
            except Exception:
                self.logger().exception("Unexpected error while sending ping")
                break

    async def _on_ws_connection_error(self, websocket_assistant: Optional[WSAssistant]):
        """
        Clean up ping task when WebSocket connection is lost.
        """
        if self._ping_task is not None:
            self._ping_task.cancel()
            self._ping_task = None

    async def subscribe_to_trading_pair(self, trading_pair: str):
        """
        Subscribe to a single trading pair's channels.
        Called when dynamically adding trading pairs.
        """
        if self._ws_assistant is None:
            return

        market_addr = await self._connector.get_market_addr_for_pair(trading_pair)

        # Store mapping for WebSocket message routing
        self._market_addr_to_trading_pair[market_addr] = trading_pair

        # Subscribe to order book
        subscribe_orderbook_request = WSJSONRequest({
            "method": "subscribe",
            "topic": f"{CONSTANTS.WS_MARKET_DEPTH_CHANNEL}:{market_addr}:1"
        })
        await self._ws_assistant.send(subscribe_orderbook_request)

        # Subscribe to trades
        subscribe_trades_request = WSJSONRequest({
            "method": "subscribe",
            "topic": f"{CONSTANTS.WS_MARKET_TRADES_CHANNEL}:{market_addr}"
        })
        await self._ws_assistant.send(subscribe_trades_request)

        # Subscribe to prices (funding)
        subscribe_prices_request = WSJSONRequest({
            "method": "subscribe",
            "topic": f"{CONSTANTS.WS_MARKET_PRICE_CHANNEL}:{market_addr}"
        })
        await self._ws_assistant.send(subscribe_prices_request)

    async def unsubscribe_from_trading_pair(self, trading_pair: str):
        """
        Unsubscribe from a single trading pair's channels.
        Called when dynamically removing trading pairs.
        """
        if self._ws_assistant is None:
            return

        market_addr = await self._connector.get_market_addr_for_pair(trading_pair)

        # Unsubscribe from order book
        unsubscribe_orderbook_request = WSJSONRequest({
            "method": "unsubscribe",
            "topic": f"{CONSTANTS.WS_MARKET_DEPTH_CHANNEL}:{market_addr}:1"
        })
        await self._ws_assistant.send(unsubscribe_orderbook_request)

        # Unsubscribe from trades
        unsubscribe_trades_request = WSJSONRequest({
            "method": "unsubscribe",
            "topic": f"{CONSTANTS.WS_MARKET_TRADES_CHANNEL}:{market_addr}"
        })
        await self._ws_assistant.send(unsubscribe_trades_request)

        # Unsubscribe from prices (funding)
        unsubscribe_prices_request = WSJSONRequest({
            "method": "unsubscribe",
            "topic": f"{CONSTANTS.WS_MARKET_PRICE_CHANNEL}:{market_addr}"
        })
        await self._ws_assistant.send(unsubscribe_prices_request)
