import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.extended import extended_constants as CONSTANTS, extended_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.extended.extended_exchange import ExtendedExchange


class ExtendedAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "ExtendedExchange",
        api_factory: Optional[WebAssistantsFactory] = None,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._trade_messages_queue_key = CONSTANTS.TRADES_CHANNEL
        self._diff_messages_queue_key = CONSTANTS.ORDERBOOK_CHANNEL

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        try:
            exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            rest_assistant = await self._api_factory.get_rest_assistant()
            
            params = {"market_id": exchange_symbol}
            data = await rest_assistant.execute_request(
                url=web_utils.public_rest_url(path_url=CONSTANTS.ORDER_BOOK_PATH_URL),
                params=params,
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.ORDER_BOOK_PATH_URL,
            )
            
            return data
        except Exception as e:
            self.logger().error(f"Error requesting order book for {trading_pair}: {e}")
            raise

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            for trading_pair in self._trading_pairs:
                trading_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                
                # Subscribe to order book updates
                orderbook_payload = {
                    "type": "subscribe",
                    "channel": CONSTANTS.ORDERBOOK_CHANNEL,
                    "market_id": trading_symbol
                }
                await ws.send(WSJSONRequest(payload=orderbook_payload))
                
                # Subscribe to trades
                trades_payload = {
                    "type": "subscribe",
                    "channel": CONSTANTS.TRADES_CHANNEL,
                    "market_id": trading_symbol
                }
                await ws.send(WSJSONRequest(payload=trades_payload))

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Error subscribing to channels: {e}", exc_info=True)
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates and connects to a websocket assistant for Extended
        """
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WS_URL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)

        # Parse Extended order book response
        bids = []
        asks = []
        update_id: float = 0

        # Extended returns order book in format: { "bids": [[price, size], ...], "asks": [[price, size], ...], "timestamp": ... }
        if isinstance(snapshot_response, dict):
            bids = snapshot_response.get("bids", [])
            asks = snapshot_response.get("asks", [])
            
            # Get timestamp/update_id
            timestamp = snapshot_response.get("timestamp") or snapshot_response.get("last_update_id")
            if timestamp:
                update_id = float(timestamp)
            else:
                update_id = self._connector.current_timestamp
        else:
            raise ValueError(f"Unexpected order book snapshot format from Extended: {snapshot_response}")

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": bids,
            "asks": asks,
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT, order_book_message_content, update_id
        )

        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parse trade messages from Extended websocket
        Expected format: {"channel": "trades", "market_id": "...", "data": {"price": ..., "size": ..., "side": ..., "timestamp": ...}}
        """
        if not isinstance(raw_message, dict):
            return
            
        market_id = raw_message.get("market_id")
        if not market_id:
            return
            
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=market_id)
        
        trade_data = raw_message.get("data", {})
        if isinstance(trade_data, list):
            # Handle multiple trades
            for trade in trade_data:
                await self._process_single_trade(trade, trading_pair, message_queue)
        else:
            # Handle single trade
            await self._process_single_trade(trade_data, trading_pair, message_queue)

    async def _process_single_trade(self, trade_data: Dict[str, Any], trading_pair: str, message_queue: asyncio.Queue):
        """Process a single trade"""
        timestamp = trade_data.get("timestamp", 0)
        if isinstance(timestamp, str):
            timestamp = float(timestamp)
        timestamp = timestamp / 1000 if timestamp > 1e12 else timestamp
        
        side = trade_data.get("side", "").lower()
        trade_type = TradeType.BUY if side == "buy" else TradeType.SELL
        
        message_content = {
            "trade_id": trade_data.get("id", timestamp),
            "trading_pair": trading_pair,
            "trade_type": float(trade_type.value),
            "amount": Decimal(str(trade_data.get("size", 0))),
            "price": Decimal(str(trade_data.get("price", 0))),
        }
        trade_message: Optional[OrderBookMessage] = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE, content=message_content, timestamp=timestamp
        )

        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parse order book diff messages from Extended websocket
        Expected format: {"channel": "orderbook", "market_id": "...", "data": {"bids": [...], "asks": [...], "timestamp": ...}}
        """
        if not isinstance(raw_message, dict):
            return
            
        market_id = raw_message.get("market_id")
        if not market_id:
            return
            
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=market_id)
        
        diff_data = raw_message.get("data", {})
        timestamp = diff_data.get("timestamp", 0)
        if isinstance(timestamp, str):
            timestamp = float(timestamp)
        timestamp = timestamp / 1000 if timestamp > 1e12 else timestamp

        message_content = {
            "trading_pair": trading_pair,
            "update_id": timestamp,
            "bids": diff_data.get("bids", []),
            "asks": diff_data.get("asks", []),
        }
        diff_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.DIFF, message_content, timestamp)

        message_queue.put_nowait(diff_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        """
        Identify which channel a message came from
        """
        channel = ""
        if not isinstance(event_message, dict):
            return channel
            
        msg_channel = event_message.get("channel", "")
        if msg_channel == CONSTANTS.TRADES_CHANNEL:
            channel = self._trade_messages_queue_key
        elif msg_channel == CONSTANTS.ORDERBOOK_CHANNEL:
            channel = self._diff_messages_queue_key
            
        return channel

    async def _process_message_for_unknown_channel(
        self, event_message: Dict[str, Any], websocket_assistant: WSAssistant
    ):
        """
        Processes a message coming from a not identified channel.
        Handle pings/pongs and other control messages
        """
        if not isinstance(event_message, dict):
            return
            
        msg_type = event_message.get("type", "")
        if msg_type == "ping":
            pong_payload = {"type": "pong"}
            pong_request = WSJSONRequest(payload=pong_payload)
            await websocket_assistant.send(request=pong_request)

