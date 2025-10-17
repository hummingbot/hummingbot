import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.asterdex import asterdex_constants as CONSTANTS, asterdex_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.asterdex.asterdex_exchange import AsterdexExchange


class AsterdexAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "AsterdexExchange",
        api_factory: Optional[WebAssistantsFactory] = None,
    ):
        print(f"🚨 ASTERDEX ORDER BOOK DATA SOURCE INITIALIZED 🚨")
        print(f"🚨 Trading pairs: {trading_pairs} 🚨")
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_TOPIC_ID
        self._diff_messages_queue_key = CONSTANTS.DIFF_TOPIC_ID
        self._api_factory = api_factory
        self.logger().critical(f"🚨 ASTERDEX ORDER BOOK DATA SOURCE INITIALIZED WITH PAIRS: {trading_pairs} 🚨")

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        try:
            print(f"🚨 REQUESTING ORDER BOOK SNAPSHOT FOR {trading_pair} 🚨")
            self.logger().critical(f"🚨 REQUESTING ORDER BOOK SNAPSHOT FOR {trading_pair} 🚨")
            
            exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            self.logger().info(f"Requesting order book for {trading_pair} -> {exchange_symbol}")
            
            # AsterDex depth endpoint requires a limit; try fallbacks if empty
            limits_to_try = [1000, 500, 100]
            last_data: Dict[str, Any] = {}
            rest_assistant = await self._api_factory.get_rest_assistant()
            for idx, limit in enumerate(limits_to_try):
                params = {"symbol": exchange_symbol, "limit": limit}
                self.logger().info(f"Order book request attempt {idx+1}/{len(limits_to_try)} params: {params}")
                data = await rest_assistant.execute_request(
                    url=web_utils.public_rest_url(path_url=CONSTANTS.DEPTH_PATH_URL),
                    params=params,
                    method=RESTMethod.GET,
                    throttler_limit_id=CONSTANTS.DEPTH_PATH_URL,
                )
                last_data = data if isinstance(data, dict) else {}
                bids_len = len(last_data.get("bids", [])) if isinstance(last_data.get("bids"), list) else 0
                asks_len = len(last_data.get("asks", [])) if isinstance(last_data.get("asks"), list) else 0
                self.logger().info(f"Depth response sizes (bids, asks): ({bids_len}, {asks_len}) for limit {limit}")
                if bids_len > 0 or asks_len > 0:
                    self.logger().info("✅ Non-empty depth received; using this snapshot")
                    return last_data

            self.logger().warning("⚠️ All depth attempts returned empty book; returning last response")
            self.logger().info(f"Last order book response for {trading_pair}: {last_data}")
            return last_data
        except Exception as e:
            self.logger().error(f"❌ Error requesting order book for {trading_pair}: {e}")
            raise

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            print("🚨 SUBSCRIBE CHANNELS METHOD CALLED! 🚨")
            self.logger().critical("🚨 SUBSCRIBE CHANNELS METHOD CALLED! 🚨")
            
            self.logger().info("=" * 50)
            self.logger().info("WEBSOCKET SUBSCRIPTION STARTING")
            self.logger().info("=" * 50)
            self.logger().info(f"Trading pairs to subscribe: {self._trading_pairs}")
            
            for trading_pair in self._trading_pairs:
                trading_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                self.logger().info(f"Subscribing to {trading_pair} -> {trading_symbol}")
                
                for topic in [CONSTANTS.DIFF_TOPIC_ID, CONSTANTS.TRADE_TOPIC_ID]:
                    payload = {"op": CONSTANTS.SUB_ENDPOINT_NAME, "ch": f"{topic}:{trading_symbol}"}
                    self.logger().info(f"Sending subscription payload: {payload}")
                    await ws.send(WSJSONRequest(payload=payload))
                    self.logger().info(f"✅ Sent subscription for {topic}:{trading_symbol}")

            self.logger().info("✅ Subscribed to public order book and trade channels...")
            self.logger().info("=" * 50)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"❌ Error subscribing to channels: {e}", exc_info=True)
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        # CRITICAL: This method is being called!
        print("🚨 WEBSOCKET CONNECTION METHOD CALLED! 🚨")
        self.logger().critical("🚨 WEBSOCKET CONNECTION METHOD CALLED! 🚨")
        
        # Add a small delay to make sure the log is written
        import asyncio
        await asyncio.sleep(0.1)
        
        # Try multiple WebSocket URL formats for AsterDex Spot API
        ws_urls_to_try = [
            CONSTANTS.WS_URL,  # wss://stream.asterdex.com
            f"{CONSTANTS.WS_URL}/ws",  # wss://stream.asterdex.com/ws
            f"{CONSTANTS.WS_URL}/stream",  # wss://stream.asterdex.com/stream
            "wss://stream.asterdex.com/ws",  # Direct connection
            "wss://stream.asterdex.com/stream",  # Direct stream
        ]
        
        self.logger().info("=" * 50)
        self.logger().info("WEBSOCKET CONNECTION ATTEMPT")
        self.logger().info("=" * 50)
        self.logger().info(f"Will try {len(ws_urls_to_try)} WebSocket URLs")
        self.logger().info(f"CONSTANTS.WS_URL = {CONSTANTS.WS_URL}")
        self.logger().info(f"CONSTANTS.WS_CONNECTION_TIMEOUT = {CONSTANTS.WS_CONNECTION_TIMEOUT}")
        
        last_error = None
        for i, ws_url in enumerate(ws_urls_to_try):
            self.logger().info(f"Attempt {i+1}/{len(ws_urls_to_try)}: {ws_url}")
            try:
                ws: WSAssistant = await self._api_factory.get_ws_assistant()
                # Add timeout to prevent hanging
                import asyncio
                self.logger().info(f"Attempting to connect to {ws_url}...")
                await asyncio.wait_for(ws.connect(ws_url=ws_url), timeout=CONSTANTS.WS_CONNECTION_TIMEOUT)
                self.logger().info(f"✅ WebSocket connected successfully to {ws_url}!")
                self.logger().info("✅ Networking should now be ready!")
                
                # Test if we can send a ping to verify the connection
                try:
                    ping_payload = {"op": "ping"}
                    await ws.send(WSJSONRequest(payload=ping_payload))
                    self.logger().info("✅ WebSocket ping sent successfully")
                except Exception as ping_error:
                    self.logger().warning(f"WebSocket ping failed: {ping_error}")
                
                return ws
            except asyncio.TimeoutError:
                self.logger().error(f"❌ WebSocket connection timeout after {CONSTANTS.WS_CONNECTION_TIMEOUT}s for {ws_url}")
                last_error = f"Timeout connecting to {ws_url}"
            except Exception as e:
                self.logger().error(f"❌ Failed to connect to WebSocket {ws_url}: {e}")
                last_error = f"Error connecting to {ws_url}: {e}"
        
        # If all attempts failed
        self.logger().error("❌ All WebSocket connection attempts failed!")
        self.logger().error(f"Last error: {last_error}")
        raise Exception(f"Failed to connect to any WebSocket URL. Last error: {last_error}")

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)

        # Debug: Log the full response structure
        self.logger().info(f"🔍 ORDER BOOK SNAPSHOT DEBUG for {trading_pair}")
        self.logger().info(f"Response type: {type(snapshot_response)}")
        self.logger().info(f"Response keys: {list(snapshot_response.keys()) if isinstance(snapshot_response, dict) else 'Not a dict'}")
        self.logger().info(f"Full response: {snapshot_response}")

        # Robust parsing to support multiple response shapes (Binance-like or nested)
        bids = None
        asks = None
        update_id: float = 0

        # Case 1: Binance-style { lastUpdateId, bids, asks }
        if isinstance(snapshot_response, dict) and "bids" in snapshot_response and "asks" in snapshot_response:
            bids = snapshot_response.get("bids", [])
            asks = snapshot_response.get("asks", [])
            # Use lastUpdateId if present, else current time
            lui = snapshot_response.get("lastUpdateId")
            if isinstance(lui, (int, float)):
                update_id = float(lui)
            else:
                update_id = self._connector.current_timestamp
            self.logger().info(f"✅ Parsed as Binance-style format")

        # Case 2: Nested under data / data.data with timestamp ts and arrays
        elif isinstance(snapshot_response, dict) and "data" in snapshot_response:
            inner = snapshot_response.get("data") or {}
            # Some APIs nest again under data
            if isinstance(inner, dict) and "data" in inner:
                inner = inner.get("data") or {}
            bids = inner.get("bids") if isinstance(inner, dict) else None
            asks = inner.get("asks") if isinstance(inner, dict) else None
            ts = inner.get("ts") if isinstance(inner, dict) else None
            if isinstance(ts, (int, float)):
                update_id = float(ts) / 1000
            else:
                update_id = self._connector.current_timestamp
            self.logger().info(f"✅ Parsed as nested data format")

        # Case 3: Direct array format (some APIs return arrays directly)
        elif isinstance(snapshot_response, list) and len(snapshot_response) >= 2:
            # Assume first element is bids, second is asks
            bids = snapshot_response[0] if len(snapshot_response) > 0 else []
            asks = snapshot_response[1] if len(snapshot_response) > 1 else []
            update_id = self._connector.current_timestamp
            self.logger().info(f"✅ Parsed as direct array format")

        # Fallback: if structure is unexpected, raise a clear error
        if bids is None or asks is None:
            self.logger().error(f"❌ Unexpected order book snapshot format: {snapshot_response}")
            raise ValueError("Unexpected order book snapshot format from AsterDex depth endpoint")

        self.logger().info(f"✅ Successfully parsed order book: {len(bids)} bids, {len(asks)} asks")
        self.logger().info(f"Sample bids: {bids[:2] if bids else 'None'}")
        self.logger().info(f"Sample asks: {asks[:2] if asks else 'None'}")

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

    async def listen_for_subscriptions(self):
        """
        Override the base class method to add debugging
        """
        print("🚨 LISTEN FOR SUBSCRIPTIONS METHOD CALLED! 🚨")
        self.logger().critical("🚨 LISTEN FOR SUBSCRIPTIONS METHOD CALLED! 🚨")
        
        # Call the parent method
        await super().listen_for_subscriptions()

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["symbol"])
        for trade_data in raw_message["data"]:
            timestamp: float = trade_data["ts"] / 1000
            message_content = {
                "trade_id": timestamp,  # trade id isn't provided so using timestamp instead
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.BUY.value) if trade_data["bm"] else float(TradeType.SELL.value),
                "amount": Decimal(trade_data["q"]),
                "price": Decimal(trade_data["p"]),
            }
            trade_message: Optional[OrderBookMessage] = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE, content=message_content, timestamp=timestamp
            )

            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        diff_data: Dict[str, Any] = raw_message["data"]
        timestamp: float = diff_data["ts"] / 1000

        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["symbol"])

        message_content = {
            "trading_pair": trading_pair,
            "update_id": timestamp,
            "bids": diff_data["bids"],
            "asks": diff_data["asks"],
        }
        diff_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.DIFF, message_content, timestamp)

        message_queue.put_nowait(diff_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        # Check if event_message is a dictionary before calling .get()
        if not isinstance(event_message, dict):
            return channel
            
        if "data" in event_message:
            event_channel = event_message.get("m")
            if event_channel == CONSTANTS.TRADE_TOPIC_ID:
                channel = self._trade_messages_queue_key
            if event_channel == CONSTANTS.DIFF_TOPIC_ID:
                channel = self._diff_messages_queue_key
        return channel

    async def _process_message_for_unknown_channel(
        self, event_message: Dict[str, Any], websocket_assistant: WSAssistant
    ):
        """
        Processes a message coming from a not identified channel.
        Does nothing by default but allows subclasses to reimplement

        :param event_message: the event received through the websocket connection
        :param websocket_assistant: the websocket connection to use to interact with the exchange
        """
        # Check if event_message is a dictionary before calling .get()
        if not isinstance(event_message, dict):
            return
            
        if event_message.get("m") == "ping":
            pong_payloads = {"op": "pong"}
            pong_request = WSJSONRequest(payload=pong_payloads)
            await websocket_assistant.send(request=pong_request)
