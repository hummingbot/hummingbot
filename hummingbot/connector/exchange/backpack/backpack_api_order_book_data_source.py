"""Backpack API order book data source."""
import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS
from hummingbot.connector.exchange.backpack.backpack_order_book import BackpackOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange


class BackpackAPIOrderBookDataSource(OrderBookTrackerDataSource):
    """
    Order book data source for Backpack Exchange.
    
    Handles fetching order book snapshots and subscribing to WebSocket streams
    for real-time order book updates.
    """

    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60
    _DYNAMIC_SUBSCRIBE_ID_START = 100

    _logger: Optional[HummingbotLogger] = None
    _next_subscribe_id: int = _DYNAMIC_SUBSCRIBE_ID_START

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "BackpackExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        """
        Initializes the order book data source.
        
        :param trading_pairs: List of trading pairs to track
        :param connector: The Backpack exchange connector
        :param api_factory: Web assistants factory
        :param domain: Domain for the API
        """
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trade_messages_queue_key = CONSTANTS.WS_TRADE_EVENT
        self._diff_messages_queue_key = CONSTANTS.WS_ORDER_BOOK_EVENT

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        Gets the last traded prices for the specified trading pairs.
        
        :param trading_pairs: List of trading pairs
        :param domain: Optional domain override
        :return: Dictionary mapping trading pairs to prices
        """
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Requests an order book snapshot from the REST API.
        
        :param trading_pair: The trading pair
        :return: Order book snapshot data
        """
        from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils
        from hummingbot.connector.exchange.backpack.backpack_utils import get_backpack_trading_pair
        
        symbol = get_backpack_trading_pair(trading_pair)
        params = {
            "symbol": symbol,
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.DEPTH_PATH_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.DEPTH_PATH_URL,
        )

        return data

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to WebSocket channels for order book and trade updates.
        
        :param ws: WebSocket assistant
        """
        try:
            from hummingbot.connector.exchange.backpack.backpack_utils import get_backpack_trading_pair
            
            trade_params = []
            depth_params = []
            ticker_params = []
            
            for trading_pair in self._trading_pairs:
                symbol = get_backpack_trading_pair(trading_pair)
                trade_params.append(f"trade.{symbol}")
                depth_params.append(f"depth.{symbol}")
                ticker_params.append(f"ticker.{symbol}")

            # Subscribe to trade stream
            if trade_params:
                payload = {
                    "method": "subscribe",
                    "params": trade_params,
                }
                subscribe_trade_request = WSJSONRequest(payload=payload)
                await ws.send(subscribe_trade_request)

            # Subscribe to depth stream
            if depth_params:
                payload = {
                    "method": "subscribe",
                    "params": depth_params,
                }
                subscribe_depth_request = WSJSONRequest(payload=payload)
                await ws.send(subscribe_depth_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True,
            )
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates and connects a WebSocket assistant.
        
        :return: Connected WebSocket assistant
        """
        from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils
        
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=web_utils.ws_url(self._domain),
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
        )
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Gets an order book snapshot message.
        
        :param trading_pair: The trading pair
        :return: Order book snapshot message
        """
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = BackpackOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parses a trade message from WebSocket.
        
        :param raw_message: Raw WebSocket message
        :param message_queue: Queue to put parsed message
        """
        if raw_message.get("e") == "trade":
            symbol = raw_message.get("s")
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
            trade_message = BackpackOrderBook.trade_message_from_exchange(
                raw_message,
                metadata={"trading_pair": trading_pair}
            )
            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parses an order book diff message from WebSocket.
        
        :param raw_message: Raw WebSocket message
        :param message_queue: Queue to put parsed message
        """
        if raw_message.get("e") == "depth":
            symbol = raw_message.get("s")
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
            order_book_message: OrderBookMessage = BackpackOrderBook.diff_message_from_exchange(
                raw_message,
                time.time(),
                metadata={"trading_pair": trading_pair}
            )
            message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        """
        Determines which channel a message originated from.
        
        :param event_message: The event message
        :return: Channel identifier
        """
        event_type = event_message.get("e")
        if event_type == CONSTANTS.WS_ORDER_BOOK_EVENT:
            return self._diff_messages_queue_key
        elif event_type == CONSTANTS.WS_TRADE_EVENT:
            return self._trade_messages_queue_key
        return ""

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        """
        Subscribes to a specific trading pair.
        
        :param trading_pair: The trading pair to subscribe to
        :return: True if successful
        """
        if self._ws_assistant is None:
            self.logger().warning(f"Cannot subscribe to {trading_pair}: WebSocket not connected")
            return False

        try:
            from hummingbot.connector.exchange.backpack.backpack_utils import get_backpack_trading_pair
            
            symbol = get_backpack_trading_pair(trading_pair)
            
            # Subscribe to trade and depth streams
            payload = {
                "method": "subscribe",
                "params": [f"trade.{symbol}", f"depth.{symbol}"],
            }
            subscribe_request = WSJSONRequest(payload=payload)
            await self._ws_assistant.send(subscribe_request)

            self.add_trading_pair(trading_pair)
            self.logger().info(f"Subscribed to {trading_pair} channels")
            return True

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Unexpected error subscribing to {trading_pair} channels")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        """
        Unsubscribes from a specific trading pair.
        
        :param trading_pair: The trading pair to unsubscribe from
        :return: True if successful
        """
        if self._ws_assistant is None:
            self.logger().warning(f"Cannot unsubscribe from {trading_pair}: WebSocket not connected")
            return False

        try:
            from hummingbot.connector.exchange.backpack.backpack_utils import get_backpack_trading_pair
            
            symbol = get_backpack_trading_pair(trading_pair)
            
            payload = {
                "method": "unsubscribe",
                "params": [f"trade.{symbol}", f"depth.{symbol}"],
            }
            unsubscribe_request = WSJSONRequest(payload=payload)
            await self._ws_assistant.send(unsubscribe_request)

            self.remove_trading_pair(trading_pair)
            self.logger().info(f"Unsubscribed from {trading_pair} channels")
            return True

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Unexpected error unsubscribing from {trading_pair} channels")
            return False
