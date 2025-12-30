import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.backpack import (
    backpack_constants as CONSTANTS,
    backpack_web_utils as web_utils,
)
from hummingbot.connector.exchange.backpack.backpack_order_book import BackpackOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange


class BackpackAPIOrderBookDataSource(OrderBookTrackerDataSource):
    """
    Order book data source for Backpack Exchange.

    Handles:
    - REST order book snapshots
    - WebSocket order book diff updates
    - WebSocket trade events
    """

    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "BackpackExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        """
        Initialize the order book data source.

        Args:
            trading_pairs: List of trading pairs to track
            connector: The exchange connector instance
            api_factory: Factory for creating API assistants
            domain: Exchange domain (mainnet or testnet)
        """
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
        """
        Get last traded prices for trading pairs.

        Args:
            trading_pairs: List of trading pairs
            domain: Optional domain override

        Returns:
            Dict mapping trading pair to last price
        """
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Request order book snapshot from REST API.

        Args:
            trading_pair: The trading pair to get snapshot for

        Returns:
            Order book snapshot data
        """
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair
        )

        params = {
            "symbol": ex_trading_pair,
            "limit": 1000,  # Max depth
        }

        data = await self._connector._api_get(
            path_url=CONSTANTS.DEPTH_URL,
            params=params,
        )
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Get order book snapshot as OrderBookMessage.

        Args:
            trading_pair: The trading pair

        Returns:
            OrderBookMessage with snapshot data
        """
        import time

        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()

        snapshot_msg: OrderBookMessage = BackpackOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair},
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Create and connect a WebSocket assistant.

        Returns:
            Connected WSAssistant
        """
        url = web_utils.wss_url(self._domain)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribe to trade and order book channels.

        Args:
            ws: The WebSocket assistant to use for subscriptions
        """
        try:
            streams = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(
                    trading_pair=trading_pair
                )
                # Add depth and trade streams
                streams.append(f"{CONSTANTS.WS_DEPTH_CHANNEL}.{symbol}")
                streams.append(f"{CONSTANTS.WS_TRADE_CHANNEL}.{symbol}")

            # Subscribe to all streams in one message
            subscribe_payload = {
                "method": "SUBSCRIBE",
                "params": streams,
            }
            subscribe_request: WSJSONRequest = WSJSONRequest(payload=subscribe_payload)
            await ws.send(subscribe_request)

            self.logger().info(
                f"Subscribed to public order book and trade channels for {len(self._trading_pairs)} pairs"
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book data streams.",
                exc_info=True,
            )
            raise

    async def _parse_order_book_diff_message(
        self,
        raw_message: Dict[str, Any],
        message_queue: asyncio.Queue,
    ):
        """
        Parse order book diff message from WebSocket.

        Args:
            raw_message: Raw WebSocket message
            message_queue: Queue to put parsed message
        """
        data = raw_message.get("data", raw_message)
        stream = raw_message.get("stream", "")

        # Extract symbol from stream name (e.g., "depth.BTC_USDC")
        symbol = stream.split(".")[-1] if "." in stream else data.get("s", "")

        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)

        timestamp: float = float(data.get("T", 0)) / 1e6 if "T" in data else None
        if timestamp is None:
            import time
            timestamp = time.time()

        order_book_message: OrderBookMessage = BackpackOrderBook.diff_message_from_exchange(
            raw_message,
            timestamp,
            {"trading_pair": trading_pair},
        )
        message_queue.put_nowait(order_book_message)

    async def _parse_order_book_snapshot_message(
        self,
        raw_message: Dict[str, Any],
        message_queue: asyncio.Queue,
    ):
        """
        Parse order book snapshot message.

        Args:
            raw_message: Raw message data
            message_queue: Queue to put parsed message
        """
        data = raw_message.get("data", raw_message)
        stream = raw_message.get("stream", "")

        symbol = stream.split(".")[-1] if "." in stream else data.get("s", "")
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)

        timestamp: float = float(data.get("T", 0)) / 1e6 if "T" in data else None
        if timestamp is None:
            import time
            timestamp = time.time()

        snapshot_message: OrderBookMessage = BackpackOrderBook.snapshot_message_from_exchange(
            data,
            timestamp,
            {"trading_pair": trading_pair},
        )
        message_queue.put_nowait(snapshot_message)

    async def _parse_trade_message(
        self,
        raw_message: Dict[str, Any],
        message_queue: asyncio.Queue,
    ):
        """
        Parse trade message from WebSocket.

        Args:
            raw_message: Raw WebSocket message
            message_queue: Queue to put parsed message
        """
        data = raw_message.get("data", raw_message)
        stream = raw_message.get("stream", "")

        symbol = stream.split(".")[-1] if "." in stream else data.get("s", "")
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)

        # Handle single trade or array of trades
        trades = data if isinstance(data, list) else [data]

        for trade_data in trades:
            trade_message: OrderBookMessage = BackpackOrderBook.trade_message_from_exchange(
                trade_data,
                {"trading_pair": trading_pair},
            )
            message_queue.put_nowait(trade_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        """
        Determine which channel a message originated from.

        Args:
            event_message: The WebSocket event message

        Returns:
            Channel key string
        """
        channel = ""
        stream = event_message.get("stream", "")

        if stream:
            if stream.startswith(CONSTANTS.WS_DEPTH_CHANNEL):
                channel = self._diff_messages_queue_key
            elif stream.startswith(CONSTANTS.WS_TRADE_CHANNEL):
                channel = self._trade_messages_queue_key

        return channel
