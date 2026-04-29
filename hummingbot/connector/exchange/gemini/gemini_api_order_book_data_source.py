import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS, gemini_web_utils as web_utils
from hummingbot.connector.exchange.gemini.gemini_order_book import GeminiOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.gemini.gemini_exchange import GeminiExchange


class GeminiAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'GeminiExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
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
        symbol = self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(
                path_url=CONSTANTS.ORDER_BOOK_PATH_URL.format(symbol=symbol),
                domain=self._domain),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDER_BOOK_PATH_URL,
        )
        return data

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=web_utils.wss_market_data_url(domain=self._domain),
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        # Gemini REST order book returns {"bids": [{"price": "...", "amount": "...", ...}], "asks": [...]}
        bids = [[entry["price"], entry["amount"]] for entry in snapshot.get("bids", [])]
        asks = [[entry["price"], entry["amount"]] for entry in snapshot.get("asks", [])]
        snapshot_msg: OrderBookMessage = GeminiOrderBook.snapshot_message_from_exchange(
            {"bids": bids, "asks": asks},
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # Trades are handled inside _parse_order_book_diff_message because
        # Gemini bundles trades and order-book changes in the same l2_updates
        # message, and the base class routes each message to only one queue.
        pass

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        msg_type = raw_message.get("type", "")
        if msg_type != "l2_updates":
            return

        symbol = raw_message.get("symbol", "").lower()
        trading_pair = self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)

        # Process order book changes
        changes = raw_message.get("changes", [])
        if changes:
            bids = [[c[1], c[2]] for c in changes if c[0] == "buy"]
            asks = [[c[1], c[2]] for c in changes if c[0] == "sell"]
            diff_msg = GeminiOrderBook.diff_message_from_exchange(
                {"bids": bids, "asks": asks},
                time.time(),
                metadata={"trading_pair": trading_pair}
            )
            message_queue.put_nowait(diff_msg)

        # Process trades bundled in the same message
        trades = raw_message.get("trades", [])
        for trade in trades:
            trade_message = GeminiOrderBook.trade_message_from_exchange(
                {"trade": trade},
                metadata={"trading_pair": trading_pair}
            )
            message_queue.put_nowait(trade_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        # Gemini l2_updates messages can contain both order book changes AND
        # trades.  The base class routes each message to exactly one queue, so
        # we always route to the diff queue (the more critical path) and handle
        # trade extraction inside _parse_order_book_diff_message.
        msg_type = event_message.get("type", "")
        if msg_type == "l2_updates":
            return self._diff_messages_queue_key
        return ""

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            symbols = [self._connector.exchange_symbol_associated_to_pair(
                trading_pair=tp).upper() for tp in self._trading_pairs]
            payload = {
                "type": "subscribe",
                "subscriptions": [{"name": "l2", "symbols": symbols}]
            }
            await ws.send(WSJSONRequest(payload=payload))
            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot subscribe to {trading_pair}: WebSocket not connected"
            )
            return False

        symbol = self._connector.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair).upper()
        payload = {
            "type": "subscribe",
            "subscriptions": [{"name": "l2", "symbols": [symbol]}]
        }
        try:
            await self._ws_assistant.send(WSJSONRequest(payload=payload))
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error subscribing to {trading_pair}")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning(
                f"Cannot unsubscribe from {trading_pair}: WebSocket not connected"
            )
            return False

        symbol = self._connector.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair).upper()
        payload = {
            "type": "unsubscribe",
            "subscriptions": [{"name": "l2", "symbols": [symbol]}]
        }
        try:
            await self._ws_assistant.send(WSJSONRequest(payload=payload))
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                f"Unexpected error occurred unsubscribing from {trading_pair}...",
                exc_info=True
            )
            return False
