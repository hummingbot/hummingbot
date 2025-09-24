"""
Order Book Data Source for Coins.xyz Exchange Connector

This module implements REST and WebSocket-based order book data source for real-time
market data from Coins.xyz exchange, including order book snapshots and updates.
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
from hummingbot.connector.exchange.coinsxyz import coinsxyz_utils as utils
from hummingbot.connector.exchange.coinsxyz import coinsxyz_web_utils as web_utils
from hummingbot.connector.exchange.coinsxyz.coinsxyz_trades_data_source import CoinsxyzTradesDataSource
from hummingbot.connector.exchange.coinsxyz.coinsxyz_klines_data_source import CoinsxyzKlinesDataSource
from hummingbot.connector.exchange.coinsxyz.coinsxyz_ticker_data_source import CoinsxyzTickerDataSource
from hummingbot.connector.exchange.coinsxyz.coinsxyz_websocket_connection_manager import CoinsxyzWebSocketConnectionManager
from hummingbot.connector.exchange.coinsxyz.coinsxyz_websocket_message_parser import CoinsxyzWebSocketMessageParser
from hummingbot.connector.exchange.coinsxyz.coinsxyz_order_book_diff_processor import CoinsxyzOrderBookDiffProcessor
from hummingbot.connector.exchange.coinsxyz.coinsxyz_realtime_data_streams import CoinsxyzRealtimeDataStreams
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class CoinsxyzAPIOrderBookDataSource(OrderBookTrackerDataSource):
    """
    Order book data source for Coins.xyz exchange.

    This class manages REST API calls and WebSocket connections for real-time market data including
    order book snapshots, order book updates, and trade data from Coins.xyz exchange.

    Features:
    - REST API order book snapshot retrieval
    - WebSocket real-time order book updates
    - Trade data streaming
    - Proper error handling and reconnection logic
    """
    
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: Any,
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        """
        Initialize the order book data source.

        :param trading_pairs: List of trading pairs to track
        :param connector: The exchange connector instance
        :param api_factory: Web assistants factory for API communication
        :param domain: API domain to use
        """
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._ws_assistant: Optional[WSAssistant] = None

        # Initialize data sources
        self._trades_data_source = CoinsxyzTradesDataSource(api_factory, domain)
        self._klines_data_source = CoinsxyzKlinesDataSource(api_factory, domain)
        self._ticker_data_source = CoinsxyzTickerDataSource(api_factory, domain)

        # Initialize WebSocket components
        self._ws_connection_manager = CoinsxyzWebSocketConnectionManager(api_factory, domain)
        self._ws_message_parser = CoinsxyzWebSocketMessageParser()
        self._order_book_diff_processor = CoinsxyzOrderBookDiffProcessor()
        self._realtime_streams = CoinsxyzRealtimeDataStreams(api_factory, domain)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        """Get the logger for this class."""
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @property
    def last_recv_time(self) -> float:
        """Get the timestamp of the last received message."""
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def get_last_traded_prices(self,
                                   trading_pairs: List[str],
                                   domain: Optional[str] = None) -> Dict[str, float]:
        """
        Get the last traded prices for the specified trading pairs.

        Uses Coins.xyz API endpoint: GET /openapi/quote/v1/ticker/24hr

        :param trading_pairs: List of trading pairs
        :param domain: API domain (optional)
        :return: Dictionary mapping trading pairs to their last traded prices
        """
        try:
            result = {}

            # Use provided domain or default
            domain = domain or self._domain

            # Create REST assistant
            rest_assistant = await self._api_factory.get_rest_assistant()

            # Get prices for each trading pair
            for trading_pair in trading_pairs:
                try:
                    # Convert trading pair to exchange symbol format
                    symbol = utils.convert_to_exchange_trading_pair(trading_pair)

                    # Prepare request
                    url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=domain)
                    params = {"symbol": symbol}

                    # Make API request
                    response = await rest_assistant.execute_request(
                        url=url,
                        params=params,
                        method=RESTMethod.GET,
                        throttler_limit_id=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL
                    )

                    # Extract last price from response
                    data = response.get("data", response)  # Handle potential wrapper
                    last_price = float(data.get("lastPrice", 0))

                    if last_price > 0:
                        result[trading_pair] = last_price
                        self.logger().debug(f"Last traded price for {trading_pair}: {last_price}")
                    else:
                        self.logger().warning(f"Invalid last price for {trading_pair}: {last_price}")

                except Exception as e:
                    self.logger().error(f"Error fetching last traded price for {trading_pair}: {e}")
                    continue

            return result

        except Exception as e:
            self.logger().error(f"Error fetching last traded prices: {e}")
            return {}

    async def get_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Get order book snapshot for a trading pair (required abstract method).

        Args:
            trading_pair: Trading pair to get snapshot for

        Returns:
            Dictionary with order book snapshot data
        """
        try:
            # Use the internal _order_book_snapshot method and convert to dict
            snapshot_msg = await self._order_book_snapshot(trading_pair)

            # Convert OrderBookMessage to dictionary format
            return {
                "trading_pair": snapshot_msg.trading_pair,
                "update_id": snapshot_msg.update_id,
                "bids": [[str(price), str(qty)] for price, qty in snapshot_msg.bids],
                "asks": [[str(price), str(qty)] for price, qty in snapshot_msg.asks],
                "timestamp": snapshot_msg.timestamp
            }

        except Exception as e:
            self.logger().error(f"Error getting order book snapshot for {trading_pair}: {e}")
            # Return empty snapshot on error
            return {
                "trading_pair": trading_pair,
                "update_id": 0,
                "bids": [],
                "asks": [],
                "timestamp": time.time() * 1000
            }

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Get order book snapshot for a trading pair via REST API.

        Based on Coins.xyz API research:
        - Endpoint: GET /openapi/quote/v1/depth?symbol={symbol}&limit={limit}
        - Response format: {"lastUpdateId": int, "bids": [[price, qty]], "asks": [[price, qty]]}

        :param trading_pair: The trading pair to get snapshot for (e.g., "BTC-USDT")
        :return: Order book snapshot message
        """
        try:
            # Convert trading pair to exchange symbol format (BTC-USDT -> BTCUSDT)
            symbol = utils.convert_to_exchange_trading_pair(trading_pair)

            # Prepare REST API request
            url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self._domain)
            params = {
                "symbol": symbol,
                "limit": 1000  # Maximum depth for comprehensive order book
            }

            # Create REST assistant and make request
            rest_assistant = await self._api_factory.get_rest_assistant()
            response = await rest_assistant.execute_request(
                url=url,
                params=params,
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL
            )

            # Parse response data
            data = response.get("data", response)  # Handle potential wrapper

            # Extract order book data
            last_update_id = int(data.get("lastUpdateId", 0))
            bids_data = data.get("bids", [])
            asks_data = data.get("asks", [])

            # Convert to Hummingbot format
            bids = [[Decimal(str(price)), Decimal(str(qty))] for price, qty in bids_data]
            asks = [[Decimal(str(price)), Decimal(str(qty))] for price, qty in asks_data]

            # Create order book message
            snapshot_timestamp = time.time() * 1000  # Convert to milliseconds

            order_book_message_content = {
                "trading_pair": trading_pair,
                "update_id": last_update_id,
                "bids": bids,
                "asks": asks,
            }

            snapshot_msg = OrderBookMessage(
                OrderBookMessageType.SNAPSHOT,
                order_book_message_content,
                snapshot_timestamp
            )

            self.logger().info(f"Order book snapshot retrieved for {trading_pair}: "
                             f"{len(bids)} bids, {len(asks)} asks, update_id: {last_update_id}")

            return snapshot_msg

        except Exception as e:
            self.logger().error(f"Error fetching order book snapshot for {trading_pair}: {e}")
            raise

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parse trade message from WebSocket and add to queue.

        WebSocket trade message format:
        {
            "stream": "btcusdt@trade",
            "data": {
                "e": "trade",
                "E": 1756794120409,
                "s": "BTCUSDT",
                "t": 12345,
                "p": "109879.00",
                "q": "0.037611",
                "T": 1756794120409,
                "m": true
            }
        }

        :param raw_message: Raw WebSocket message
        :param message_queue: Queue to add parsed message to
        """
        try:
            # Extract data from WebSocket message
            data = raw_message.get("data", raw_message)
            stream = raw_message.get("stream", "")

            # Extract trading pair from stream
            if "@trade" in stream:
                symbol = stream.split("@")[0].upper()
                trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
            else:
                # Fallback: try to get from data
                symbol = data.get("s", "")
                trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)

            if not trading_pair:
                self.logger().warning(f"Could not determine trading pair for trade message: {raw_message}")
                return

            # Parse trade data
            trade_id = str(data.get("t", data.get("id", 0)))
            price = Decimal(str(data.get("p", data.get("price", "0"))))
            amount = Decimal(str(data.get("q", data.get("qty", "0"))))
            timestamp = float(data.get("T", data.get("time", data.get("E", 0))))

            # Convert timestamp from milliseconds to seconds if needed
            if timestamp > 1e12:  # If timestamp is in milliseconds
                timestamp = timestamp / 1000.0

            # Determine trade type (buy/sell)
            # 'm' field indicates if buyer is maker (true) or taker (false)
            is_buyer_maker = data.get("m", data.get("isBuyerMaker", False))
            trade_type = float(TradeType.SELL.value) if is_buyer_maker else float(TradeType.BUY.value)

            # Create trade message content
            message_content = {
                "trade_id": trade_id,
                "trading_pair": trading_pair,
                "trade_type": trade_type,
                "amount": str(amount),
                "price": str(price),
                "update_id": int(data.get("E", timestamp * 1000))  # Use event time as update_id
            }

            # Create OrderBookMessage
            trade_message = OrderBookMessage(
                OrderBookMessageType.TRADE,
                message_content,
                timestamp
            )

            message_queue.put_nowait(trade_message)
            self.logger().debug(f"Parsed trade message for {trading_pair}: {trade_id} at {price}")

        except Exception as e:
            self.logger().error(f"Error parsing trade message: {e}")
            self.logger().debug(f"Raw message: {raw_message}")

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parse order book diff message from WebSocket and add to queue.

        :param raw_message: Raw WebSocket message
        :param message_queue: Queue to add parsed message to
        """
        try:
            # Parse message using WebSocket message parser
            parsed_message = self._ws_message_parser.parse_message(raw_message)

            if not parsed_message:
                self.logger().warning("Failed to parse order book diff message")
                return

            # Process through diff processor
            await self._order_book_diff_processor.process_diff_message(parsed_message, message_queue)

        except Exception as e:
            self.logger().error(f"Error parsing order book diff message: {e}")
            self.logger().debug(f"Raw message: {raw_message}")

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parse order book snapshot message from WebSocket and add to queue.

        :param raw_message: Raw WebSocket message
        :param message_queue: Queue to add parsed message to
        """
        try:
            # For snapshots, we typically get them via REST API
            # This method handles any WebSocket snapshot messages if supported
            self.logger().debug("Order book snapshot message received via WebSocket")

            # Parse message using WebSocket message parser
            parsed_message = self._ws_message_parser.parse_message(raw_message)

            if not parsed_message:
                self.logger().warning("Failed to parse order book snapshot message")
                return

            # Convert to OrderBookMessage if it's a valid snapshot
            # This would be implemented based on the actual WebSocket snapshot format
            self.logger().debug(f"Parsed snapshot message: {parsed_message}")

        except Exception as e:
            self.logger().error(f"Error parsing order book snapshot message: {e}")
            self.logger().debug(f"Raw message: {raw_message}")

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Create and return a connected WebSocket assistant.
        
        :return: Connected WebSocket assistant
        """
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
            await self._ws_assistant.connect(
                ws_url=web_utils.websocket_url(self._domain),
                ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
            )
        return self._ws_assistant

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribe to WebSocket channels for market data.
        
        :param ws: WebSocket assistant to use for subscriptions
        """
        try:
            for trading_pair in self._trading_pairs:
                # Subscribe to order book updates
                symbol = trading_pair.replace("-", "").lower()
                
                # Order book depth subscription
                depth_request = WSJSONRequest({
                    "method": "SUBSCRIBE",
                    "params": [f"{symbol}@depth"],
                    "id": 1
                })
                await ws.send(depth_request)
                
                # Trade subscription
                trade_request = WSJSONRequest({
                    "method": "SUBSCRIBE", 
                    "params": [f"{symbol}@trade"],
                    "id": 2
                })
                await ws.send(trade_request)
                
                self.logger().info(f"Subscribed to {trading_pair} market data streams")
                
        except Exception as e:
            self.logger().error(f"Error subscribing to channels: {e}")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, message_queue: asyncio.Queue):
        """
        Process incoming WebSocket messages.
        
        :param websocket_assistant: WebSocket assistant receiving messages
        :param message_queue: Queue to add processed messages to
        """
        async for ws_response in websocket_assistant.iter_messages():
            try:
                data = ws_response.data
                
                # Handle different message types
                if "stream" in data:
                    stream = data["stream"]
                    if "@depth" in stream:
                        await self._parse_order_book_diff_message(data, message_queue)
                    elif "@trade" in stream:
                        await self._parse_trade_message(data, message_queue)
                        
            except Exception as e:
                self.logger().error(f"Error processing WebSocket message: {e}")
                continue

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop,
                                        output: asyncio.Queue) -> None:
        """
        Listen for order book difference messages (required abstract method).

        Args:
            ev_loop: Event loop
            output: Output queue for order book diff messages
        """
        try:
            self.logger().info("Starting order book diff listener")

            # Create WebSocket assistant
            ws_assistant = await self._api_factory.get_ws_assistant()

            # Connect to WebSocket
            ws_url = web_utils.websocket_url(domain=self._domain)
            await ws_assistant.connect(ws_url)

            # Subscribe to depth channels
            await self._subscribe_channels(ws_assistant)

            # Process messages
            await self._process_websocket_messages(ws_assistant, output)

        except Exception as e:
            self.logger().error(f"Error in order book diff listener: {e}")
        finally:
            if ws_assistant and ws_assistant.is_connected:
                await ws_assistant.disconnect()

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop,
                                            output: asyncio.Queue) -> None:
        """
        Listen for order book snapshot messages (required abstract method).

        Args:
            ev_loop: Event loop
            output: Output queue for order book snapshot messages
        """
        try:
            self.logger().info("Starting order book snapshot listener")

            # For REST-based snapshots, we periodically fetch snapshots
            while True:
                for trading_pair in self._trading_pairs:
                    try:
                        # Get snapshot via REST API
                        snapshot_msg = await self._order_book_snapshot(trading_pair)
                        await output.put(snapshot_msg)

                    except Exception as e:
                        self.logger().error(f"Error getting snapshot for {trading_pair}: {e}")

                # Wait before next snapshot fetch
                await asyncio.sleep(30)  # Fetch snapshots every 30 seconds

        except asyncio.CancelledError:
            self.logger().info("Order book snapshot listener cancelled")
        except Exception as e:
            self.logger().error(f"Error in order book snapshot listener: {e}")

    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop,
                              output: asyncio.Queue) -> None:
        """
        Listen for trade messages (required abstract method).

        Args:
            ev_loop: Event loop
            output: Output queue for trade messages
        """
        try:
            self.logger().info("Starting trade listener")

            # Create WebSocket assistant
            ws_assistant = await self._api_factory.get_ws_assistant()

            # Connect to WebSocket
            ws_url = web_utils.websocket_url(domain=self._domain)
            await ws_assistant.connect(ws_url)

            # Subscribe to trade channels
            for trading_pair in self._trading_pairs:
                symbol = utils.convert_to_exchange_trading_pair(trading_pair)
                trade_channel = f"{symbol.lower()}@trade"
                await ws_assistant.subscribe([trade_channel])

            # Process trade messages
            async for ws_response in ws_assistant.iter_messages():
                try:
                    data = ws_response.data

                    if "stream" in data and "@trade" in data["stream"]:
                        await self._parse_trade_message(data, output)

                except Exception as e:
                    self.logger().error(f"Error processing trade message: {e}")
                    continue

        except Exception as e:
            self.logger().error(f"Error in trade listener: {e}")
        finally:
            if ws_assistant and ws_assistant.is_connected:
                await ws_assistant.disconnect()

    # Klines/Candlestick Data Methods
    async def get_klines(self,
                        trading_pair: str,
                        interval: str = "1h",
                        limit: int = 500,
                        start_time: Optional[int] = None,
                        end_time: Optional[int] = None) -> List[List[Union[int, str]]]:
        """
        Get klines/candlestick data for a trading pair.

        Args:
            trading_pair: Trading pair in Hummingbot format
            interval: Kline interval (1m, 5m, 1h, 1d, etc.)
            limit: Number of klines to fetch
            start_time: Start time in milliseconds (optional)
            end_time: End time in milliseconds (optional)

        Returns:
            List of klines data
        """
        return await self._klines_data_source.get_klines(
            trading_pair, interval, limit, start_time, end_time
        )

    async def get_latest_kline(self,
                              trading_pair: str,
                              interval: str = "1h") -> Optional[List[Union[int, str]]]:
        """Get the latest kline for a trading pair."""
        return await self._klines_data_source.get_latest_kline(trading_pair, interval)

    def get_supported_kline_intervals(self) -> List[str]:
        """Get list of supported kline intervals."""
        return self._klines_data_source.get_supported_intervals()

    # Ticker Data Methods
    async def get_24hr_ticker(self, trading_pair: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Get 24hr ticker statistics.

        Args:
            trading_pair: Trading pair in Hummingbot format (optional)

        Returns:
            Ticker data (single dict if trading_pair specified, list if None)
        """
        return await self._ticker_data_source.get_24hr_ticker(trading_pair)

    async def get_best_bid_ask(self, trading_pair: str) -> Optional[Dict[str, Any]]:
        """Get best bid and ask prices for a trading pair."""
        return await self._ticker_data_source.get_best_bid_ask(trading_pair)

    async def get_price_ticker(self, trading_pair: Optional[str] = None) -> Union[Dict[str, str], List[Dict[str, str]]]:
        """Get latest price for symbol(s)."""
        return await self._ticker_data_source.get_price_ticker(trading_pair)

    async def get_ticker_statistics(self, trading_pair: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive ticker statistics for a trading pair."""
        return await self._ticker_data_source.get_ticker_statistics(trading_pair)

    # Recent Trades Methods
    async def get_recent_trades(self,
                               trading_pair: str,
                               limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trades for a trading pair."""
        return await self._trades_data_source.get_recent_trades(trading_pair, limit)

    async def get_recent_trades_messages(self,
                                       trading_pair: str,
                                       limit: int = 100) -> List[OrderBookMessage]:
        """Get recent trades as OrderBookMessage objects."""
        return await self._trades_data_source.get_recent_trades_messages(trading_pair, limit)

    async def listen_for_subscriptions(self):
        """
        Main method to listen for WebSocket subscriptions.
        
        This method manages the WebSocket connection lifecycle and message processing.
        """
        ws = None
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(ws, self._message_queue[self.DIFF_TOPIC])
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error in WebSocket connection: {e}")
                if ws:
                    await ws.disconnect()
                    self._ws_assistant = None
                await asyncio.sleep(5)  # Wait before reconnecting
