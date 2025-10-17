import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import LighterPerpetualDerivative


class LighterPerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "LighterPerpetualDerivative",
        api_factory: Optional[WebAssistantsFactory] = None,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trade_messages_queue_key = CONSTANTS.TRADES_ENDPOINT_NAME
        self._diff_messages_queue_key = CONSTANTS.DEPTH_ENDPOINT_NAME

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)
    
    async def get_funding_info(self, trading_pair: str):
        """
        Get funding info for a trading pair from Lighter
        Returns FundingInfo object with index_price, mark_price, next_funding_time, and rate
        """
        from hummingbot.core.data_type.funding_info import FundingInfo
        
        try:
            market_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            
            # Get funding rates from Lighter API
            rest_assistant = await self._api_factory.get_rest_assistant()
            
            params = {"market_id": market_symbol}
            
            response = await rest_assistant.execute_request(
                url=web_utils.public_rest_url(path_url=CONSTANTS.FUNDING_RATES_URL, domain=self._domain),
                method=RESTMethod.GET,
                params=params,
                throttler_limit_id=CONSTANTS.FUNDING_RATES_URL,
            )
            
            # Parse Lighter funding rate response
            if isinstance(response, dict):
                data = response.get("data", response)
                
                index_price = Decimal(str(data.get("index_price", 0)))
                mark_price = Decimal(str(data.get("mark_price", 0)))
                next_funding_time = int(data.get("next_funding_time", 0))
                rate = Decimal(str(data.get("funding_rate", 0)))
                
                funding_info = FundingInfo(
                    trading_pair=trading_pair,
                    index_price=index_price,
                    mark_price=mark_price,
                    next_funding_utc_timestamp=next_funding_time,
                    rate=rate,
                )
                
                return funding_info
            
        except Exception as e:
            self.logger().error(f"Error fetching funding info for {trading_pair}: {e}")
        
        # Return default funding info if failed
        from hummingbot.core.data_type.funding_info import FundingInfo
        return FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal("0"),
            mark_price=Decimal("0"),
            next_funding_utc_timestamp=0,
            rate=Decimal("0"),
        )
    
    async def listen_for_funding_info(self, output: asyncio.Queue):
        """
        Listen for funding info updates and push them to the output queue
        Lighter updates funding hourly
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    funding_info = await self.get_funding_info(trading_pair)
                    output.put_nowait(funding_info)
                
                # Wait before next update (Lighter updates funding every hour)
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error in funding info listener: {e}")
                await asyncio.sleep(60)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves order book snapshot from Lighter
        Lighter uses: GET /api/v1/orderbook?market_id={market}
        """
        try:
            exchange_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            rest_assistant = await self._api_factory.get_rest_assistant()
            
            params = {"market_id": exchange_symbol}
            
            self.logger().info(f"📖 Requesting order book for {exchange_symbol}")
            
            data = await rest_assistant.execute_request(
                url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_REST_URL, domain=self._domain),
                method=RESTMethod.GET,
                params=params,
                throttler_limit_id=CONSTANTS.SNAPSHOT_REST_URL,
            )
            
            self.logger().info(f"✅ Order book received for {trading_pair}")
            return data
        except Exception as e:
            self.logger().error(f"❌ Error requesting order book for {trading_pair}: {e}")
            raise

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to order book and trade channels
        """
        try:
            for trading_pair in self._trading_pairs:
                trading_symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                
                # Subscribe to order book
                orderbook_payload = {
                    "type": "subscribe",
                    "channel": CONSTANTS.DEPTH_ENDPOINT_NAME,
                    "market_id": trading_symbol
                }
                await ws.send(WSJSONRequest(payload=orderbook_payload))
                
                # Subscribe to trades
                trades_payload = {
                    "type": "subscribe",
                    "channel": CONSTANTS.TRADES_ENDPOINT_NAME,
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
        Creates and connects to a websocket assistant for Lighter
        """
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        
        # Build WebSocket URL for Lighter
        ws_url = web_utils.wss_url(domain=self._domain)
        
        self.logger().info(f"🔌 Connecting to Lighter WebSocket: {ws_url}")
        
        await ws.connect(ws_url=ws_url)
        self.logger().info(f"✅ WebSocket connected successfully")
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)

        bids = []
        asks = []
        update_id: float = 0

        # Parse Lighter order book response
        if isinstance(snapshot_response, dict):
            data = snapshot_response.get("data", snapshot_response)
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            timestamp = data.get("timestamp") or data.get("last_update_id")
            
            self.logger().info(f"📊 Parsed order book: {len(bids)} bids, {len(asks)} asks")
            
            if timestamp:
                update_id = float(timestamp) / 1000 if float(timestamp) > 1e12 else float(timestamp)
            else:
                update_id = self._connector.current_timestamp
        else:
            raise ValueError(f"Unexpected order book snapshot format: {snapshot_response}")

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
        Parse trade messages from Lighter websocket
        """
        if not isinstance(raw_message, dict):
            return
            
        market_id = raw_message.get("market_id")
        if not market_id:
            return
            
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=market_id)
        
        trade_data = raw_message.get("data", {})
        if isinstance(trade_data, list):
            for trade in trade_data:
                await self._process_single_trade(trade, trading_pair, message_queue)
        else:
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
        Parse order book diff messages
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
        if msg_channel == CONSTANTS.TRADES_ENDPOINT_NAME:
            channel = self._trade_messages_queue_key
        elif msg_channel == CONSTANTS.DEPTH_ENDPOINT_NAME:
            channel = self._diff_messages_queue_key
            
        return channel

    async def _process_message_for_unknown_channel(
        self, event_message: Dict[str, Any], websocket_assistant: WSAssistant
    ):
        """
        Handle pings/pongs and other control messages
        """
        if not isinstance(event_message, dict):
            return
            
        msg_type = event_message.get("type", "")
        if msg_type == "ping":
            pong_payload = {"type": "pong"}
            pong_request = WSJSONRequest(payload=pong_payload)
            await websocket_assistant.send(request=pong_request)

