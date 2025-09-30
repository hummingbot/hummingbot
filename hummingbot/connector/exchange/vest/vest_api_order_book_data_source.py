import asyncio
import logging
from typing import Any, AsyncIterable, Dict, List, Optional

from hummingbot.connector.exchange.vest import vest_constants as CONSTANTS
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class VestAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector,
                 api_factory: WebAssistantsFactory):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._trading_pairs = trading_pairs

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @property
    def exchange_symbol_associated_to_pair(self):
        return self._connector.exchange_symbol_associated_to_pair

    @property
    def trading_pair_associated_to_exchange_symbol(self):
        return self._connector.trading_pair_associated_to_exchange_symbol

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Fetch order book snapshot for a trading pair
        """
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "limit": 1000
        }

        snapshot = await self._connector._api_get(
            path_url=CONSTANTS.VEST_ORDERBOOK_PATH,
            params=params
        )

        snapshot_timestamp: float = self._time()
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=snapshot,
            timestamp=snapshot_timestamp
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Create a connected WebSocket assistant for order book data
        """
        ws_url = CONSTANTS.get_vest_ws_url(self._connector.vest_environment)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ping_timeout=self.PING_TIMEOUT)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribe to order book channels for all trading pairs
        """
        try:
            for trading_pair in self._trading_pairs:
                symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

                # Subscribe to order book updates
                depth_channel = f"{symbol}@depth"
                payload = {
                    "method": "SUBSCRIBE",
                    "params": [depth_channel],
                    "id": 1
                }
                subscribe_request = WSJSONRequest(payload=payload)
                await ws.send(subscribe_request)

                # Subscribe to trades
                trades_channel = f"{symbol}@trades"
                payload = {
                    "method": "SUBSCRIBE",
                    "params": [trades_channel],
                    "id": 2
                }
                subscribe_request = WSJSONRequest(payload=payload)
                await ws.send(subscribe_request)

            self.logger().info("Subscribed to all trading pairs")
        except Exception as e:
            self.logger().error(f"Failed to subscribe to channels: {e}")
            raise

    async def _process_websocket_messages(self, websocket: WSAssistant) -> AsyncIterable[str]:
        """
        Process incoming WebSocket messages
        """
        try:
            async for ws_response in websocket.iter_messages():
                data = ws_response.data
                yield data
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error processing websocket messages")
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        """
        Determine which channel an event message came from
        """
        channel = ""
        if "stream" in event_message:
            channel = event_message["stream"]
        return channel

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parse order book diff messages and add to queue
        """
        try:
            if "data" in raw_message:
                data = raw_message["data"]
                symbol = data.get("symbol", "")

                if symbol in self._connector._trading_pair_symbol_map:
                    trading_pair = self._connector._trading_pair_symbol_map[symbol]

                    order_book_message = OrderBookMessage(
                        message_type=OrderBookMessageType.DIFF,
                        content={
                            "trading_pair": trading_pair,
                            "update_id": data.get("lastUpdateId", 0),
                            "bids": data.get("bids", []),
                            "asks": data.get("asks", [])
                        },
                        timestamp=self._time()
                    )
                    message_queue.put_nowait(order_book_message)
        except Exception:
            self.logger().error("Error parsing order book diff message", exc_info=True)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parse trade messages and add to queue
        """
        try:
            if "data" in raw_message:
                data = raw_message["data"]
                symbol = data.get("symbol", "")

                if symbol in self._connector._trading_pair_symbol_map:
                    trading_pair = self._connector._trading_pair_symbol_map[symbol]

                    trade_message = OrderBookMessage(
                        message_type=OrderBookMessageType.TRADE,
                        content={
                            "trading_pair": trading_pair,
                            "trade_type": float(data.get("price", 0)),
                            "amount": float(data.get("quantity", 0)),
                            "price": float(data.get("price", 0)),
                            "trade_id": data.get("tradeId", ""),
                            "timestamp": data.get("timestamp", self._time())
                        },
                        timestamp=self._time()
                    )
                    message_queue.put_nowait(trade_message)
        except Exception:
            self.logger().error("Error parsing trade message", exc_info=True)
