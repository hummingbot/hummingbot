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
# Simplified imports to avoid circular dependencies
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
    
    # Message queue topics
    DIFF_TOPIC = "order_book_diff"
    TRADE_TOPIC = "trade"
    SNAPSHOT_TOPIC = "snapshot"

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

        # Message queues for base class compatibility
        self._message_queue = {}
        self._diff_messages_queue = {}
        self._trade_messages_queue = {}
        
        # Initialize queues for trading pairs
        for trading_pair in self._trading_pairs:
            self._diff_messages_queue[trading_pair] = asyncio.Queue()
            self._trade_messages_queue[trading_pair] = asyncio.Queue()

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
            self.logger().debug(f"DEBUG: Parsing trade message: {raw_message}")
            
            # Extract data from WebSocket message
            data = raw_message.get("data", raw_message)
            stream = raw_message.get("stream", "")

            # Determinar trading pair baseado no formato
            if "stream" in raw_message and ("@trade" in raw_message["stream"] or "@aggTrade" in raw_message["stream"]):
                # Formato com stream
                stream = raw_message["stream"]
                symbol = stream.split("@")[0].upper()
                self.logger().debug(f"DEBUG: Extracted symbol from stream {stream}: {symbol}")
                try:
                    trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
                except Exception as mapping_error:
                    self.logger().error(f"DEBUG: Error mapping symbol {symbol}: {mapping_error}")
                    # Fallback to utils parsing
                    try:
                        trading_pair = utils.parse_exchange_trading_pair(symbol)
                        self.logger().debug(f"DEBUG: Fallback mapping {symbol} -> {trading_pair}")
                    except Exception as fallback_error:
                        self.logger().error(f"DEBUG: Fallback mapping failed for {symbol}: {fallback_error}")
                        trading_pair = None
            else:
                # Formato direto Coins.xyz
                symbol = data.get("s", "")
                self.logger().debug(f"DEBUG: Extracted symbol from data: {symbol}")
                try:
                    trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
                except Exception as mapping_error:
                    self.logger().error(f"DEBUG: Error mapping symbol {symbol}: {mapping_error}")
                    # Fallback to utils parsing
                    try:
                        trading_pair = utils.parse_exchange_trading_pair(symbol)
                        self.logger().debug(f"DEBUG: Fallback mapping {symbol} -> {trading_pair}")
                    except Exception as fallback_error:
                        self.logger().error(f"DEBUG: Fallback mapping failed for {symbol}: {fallback_error}")
                        trading_pair = None

            self.logger().debug(f"DEBUG: Symbol {symbol} mapped to trading_pair: {trading_pair}")

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
            self.logger().debug(f"Successfully parsed trade message for {trading_pair}: {trade_id} at {price}")

        except Exception as e:
            self.logger().error(f"Error parsing trade message: {e}")
            self.logger().error(f"DEBUG: Full raw message that caused error: {raw_message}")
            self.logger().error(f"DEBUG: Message type: {type(raw_message)}")
            if isinstance(raw_message, dict):
                self.logger().error(f"DEBUG: Message keys: {list(raw_message.keys())}")
                for key, value in raw_message.items():
                    self.logger().error(f"DEBUG: {key}: {value} (type: {type(value)})")

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """Parse order book diff message from WebSocket and add to queue."""
        try:
            self.logger().debug(f"DEBUG: Parsing order book diff message: {raw_message}")
            
            # Formato Coins.xyz: {'e': 'depthUpdate', 'E': timestamp, 's': 'BTCUSDT', 'U': first_id, 'u': final_id, 'b': bids, 'a': asks}
            if "e" in raw_message and raw_message["e"] == "depthUpdate":
                symbol = raw_message.get("s", "")
                self.logger().debug(f"DEBUG: Processing depthUpdate for symbol: {symbol}")
                
                try:
                    # Try connector method first
                    trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
                    self.logger().debug(f"DEBUG: Symbol {symbol} mapped to trading_pair: {trading_pair}")
                except Exception as mapping_error:
                    self.logger().error(f"DEBUG: Error mapping symbol {symbol}: {mapping_error}")
                    # Fallback to utils parsing
                    try:
                        trading_pair = utils.parse_exchange_trading_pair(symbol)
                        self.logger().debug(f"DEBUG: Fallback mapping {symbol} -> {trading_pair}")
                    except Exception as fallback_error:
                        self.logger().error(f"DEBUG: Fallback mapping failed for {symbol}: {fallback_error}")
                        trading_pair = None
                
                if trading_pair:
                    # Converter para formato OrderBookMessage
                    bids_raw = raw_message.get("b", [])
                    asks_raw = raw_message.get("a", [])
                    self.logger().debug(f"DEBUG: Raw bids count: {len(bids_raw)}, asks count: {len(asks_raw)}")
                    
                    bids = [[Decimal(str(price)), Decimal(str(qty))] for price, qty in bids_raw]
                    asks = [[Decimal(str(price)), Decimal(str(qty))] for price, qty in asks_raw]
                    
                    message_content = {
                        "trading_pair": trading_pair,
                        "update_id": raw_message.get("u", 0),
                        "bids": bids,
                        "asks": asks,
                        "first_update_id": raw_message.get("U", 0)
                    }
                    
                    timestamp = raw_message.get("E", time.time() * 1000) / 1000.0
                    
                    diff_message = OrderBookMessage(
                        OrderBookMessageType.DIFF,
                        message_content,
                        timestamp
                    )
                    
                    await message_queue.put(diff_message)
                    self.logger().debug(f"Successfully parsed order book diff for {trading_pair}: {len(bids)} bids, {len(asks)} asks")
                else:
                    self.logger().warning(f"DEBUG: No trading_pair found for symbol: {symbol}")
            else:
                # Formato com stream (fallback)
                self.logger().debug(f"DEBUG: Message not depthUpdate format, using fallback: {raw_message}")
                await message_queue.put(raw_message)
                
        except Exception as e:
            self.logger().error(f"Error parsing order book diff message: {e}")
            self.logger().error(f"DEBUG: Full raw message that caused error: {raw_message}")
            self.logger().error(f"DEBUG: Message type: {type(raw_message)}")
            if isinstance(raw_message, dict):
                self.logger().error(f"DEBUG: Message keys: {list(raw_message.keys())}")
                for key, value in raw_message.items():
                    self.logger().error(f"DEBUG: {key}: {value} (type: {type(value)})")

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """Parse order book snapshot message from WebSocket and add to queue."""
        try:
            # Simple snapshot processing
            self.logger().debug("Order book snapshot message received via WebSocket")
            await message_queue.put(raw_message)
        except Exception as e:
            self.logger().error(f"Error parsing order book snapshot message: {e}")

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Create and return a connected WebSocket assistant.
        
        :return: Connected WebSocket assistant
        """
        try:
            # Always create a new WebSocket connection to avoid concurrent access
            ws_assistant = await self._api_factory.get_ws_assistant()
            ws_url = web_utils.websocket_url(self._domain)
            
            await asyncio.wait_for(
                ws_assistant.connect(
                    ws_url=ws_url,
                    ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
                ),
                timeout=30.0
            )
            
            self.logger().info(f"WebSocket connected to {ws_url}")
            return ws_assistant
            
        except Exception as e:
            self.logger().error(f"Failed to connect WebSocket: {e}")
            raise

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribe to WebSocket channels for market data.
        
        :param ws: WebSocket assistant to use for subscriptions
        """
        try:
            if not self._trading_pairs:
                self.logger().warning("No trading pairs available for subscription")
                return
            
            if not ws:
                raise Exception("WebSocket is not connected")
                

                

                
            for trading_pair in self._trading_pairs:
                try:
                    
                    symbol = trading_pair.replace("-", "").lower()
                    
                    # Subscrição combinada para evitar desconexão
                    combined_request = WSJSONRequest({
                        "method": "SUBSCRIBE",
                        "params": [
                            f"{symbol}@depth",
                            f"{symbol}@aggTrade"
                        ],
                        "id": 1
                    })

                    await asyncio.wait_for(ws.send(combined_request), timeout=10.0)
                    
                    self.logger().info(f"Subscribed to {trading_pair} market data streams")
                    
                except Exception as pair_error:
                    self.logger().error(f"Error subscribing to {trading_pair}: {pair_error}")
                    continue
                
        except Exception as e:
            self.logger().error(f"Error subscribing to channels: {e}")
            raise



    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop,
                                        output: asyncio.Queue) -> None:
        """
        Listen for order book difference messages (required abstract method).

        Args:
            ev_loop: Event loop
            output: Output queue for order book diff messages
        """
        ws = None
        retry_count = 0
        max_retries = 10
        
        while retry_count < max_retries:
            try:
                ws = await self._connected_websocket_assistant()
                if ws:
                    await self._subscribe_channels(ws)
                    retry_count = 0
                    
                    async for ws_response in ws.iter_messages():
                        try:
                            data = ws_response.data
                            
                            if data is None:
                                continue
                            
                            if isinstance(data, str):
                                if not data.strip():
                                    continue
                                try:
                                    import json
                                    data = json.loads(data)
                                except json.JSONDecodeError:
                                    continue
                            
                            if isinstance(data, dict):
                                # Only process order book diff messages
                                self.logger().debug(f"DEBUG: Processing message for order book diffs: {data}")
                                if "stream" in data and "@depth" in data["stream"]:
                                    self.logger().debug(f"DEBUG: Found stream depth message: {data['stream']}")
                                    await self._parse_order_book_diff_message(data, output)
                                elif "e" in data and data["e"] == "depthUpdate":
                                    self.logger().debug(f"DEBUG: Found depthUpdate message for symbol: {data.get('s', 'unknown')}")
                                    await self._parse_order_book_diff_message(data, output)
                                else:
                                    self.logger().debug(f"DEBUG: Message not recognized as order book diff: {data}")
                                    
                        except Exception as msg_error:
                            self.logger().error(f"Error processing diff message: {msg_error}")
                            self.logger().error(f"DEBUG: Message that caused diff error: {ws_response.data if hasattr(ws_response, 'data') else 'no data'}")
                            continue
                else:
                    await asyncio.sleep(5)
                    continue
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                retry_count += 1
                self.logger().error(f"Error in order book diffs listener (retry {retry_count}/{max_retries}): {e}")
                
                if ws:
                    try:
                        await asyncio.wait_for(ws.disconnect(), timeout=5.0)
                    except Exception:
                        pass
                    finally:
                        self._ws_assistant = None
                        ws = None
                
                delay = min(5 * retry_count, 30)
                await asyncio.sleep(delay)

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
        ws = None
        retry_count = 0
        max_retries = 10
        
        while retry_count < max_retries:
            try:
                ws = await self._connected_websocket_assistant()
                if ws:
                    await self._subscribe_channels(ws)
                    retry_count = 0
                    
                    async for ws_response in ws.iter_messages():
                        try:
                            data = ws_response.data
                            
                            if data is None:
                                continue
                            
                            if isinstance(data, str):
                                if not data.strip():
                                    continue
                                try:
                                    import json
                                    data = json.loads(data)
                                except json.JSONDecodeError:
                                    continue
                            
                            if isinstance(data, dict):
                                # Only process trade messages
                                self.logger().debug(f"DEBUG: Processing message for trades: {data}")
                                if "stream" in data and ("@trade" in data["stream"] or "@aggTrade" in data["stream"]):
                                    self.logger().debug(f"DEBUG: Found stream trade message: {data['stream']}")
                                    await self._parse_trade_message(data, output)
                                elif "e" in data and data["e"] == "trade":
                                    self.logger().debug(f"DEBUG: Found trade message for symbol: {data.get('s', 'unknown')}")
                                    await self._parse_trade_message(data, output)
                                else:
                                    self.logger().debug(f"DEBUG: Message not recognized as trade: {data}")
                                    
                        except Exception as msg_error:
                            self.logger().error(f"Error processing trade message: {msg_error}")
                            self.logger().error(f"DEBUG: Message that caused trade error: {ws_response.data if hasattr(ws_response, 'data') else 'no data'}")
                            continue
                else:
                    await asyncio.sleep(5)
                    continue
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                retry_count += 1
                self.logger().error(f"Error in trades listener (retry {retry_count}/{max_retries}): {e}")
                
                if ws:
                    try:
                        await asyncio.wait_for(ws.disconnect(), timeout=5.0)
                    except Exception:
                        pass
                    finally:
                        self._ws_assistant = None
                        ws = None
                
                delay = min(5 * retry_count, 30)
                await asyncio.sleep(delay)

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

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        """
        Determine the channel that originated the message (required by base class).
        
        Args:
            event_message: WebSocket message
            
        Returns:
            Channel identifier string
        """
        try:
            # Check for stream format
            if "stream" in event_message:
                return event_message["stream"]
            
            # Check for direct format with symbol
            if "s" in event_message:
                symbol = event_message["s"].lower()
                event_type = event_message.get("e", "")
                
                if event_type == "depthUpdate":
                    return f"{symbol}@depth"
                elif event_type == "trade":
                    return f"{symbol}@trade"
                elif event_type == "aggTrade":
                    return f"{symbol}@aggTrade"
            
            # Default fallback
            return "unknown"
            
        except Exception as e:
            self.logger().error(f"Error determining channel for message: {e}")
            return "unknown"

    def _trade_messages_queue_key(self, trading_pair: str) -> str:
        """
        Get the queue key for trade messages (required by base class).
        
        Args:
            trading_pair: Trading pair
            
        Returns:
            Queue key string
        """
        return f"{trading_pair}.trade"

    def _diff_messages_queue_key(self, trading_pair: str) -> str:
        """
        Get the queue key for diff messages (required by base class).
        
        Args:
            trading_pair: Trading pair
            
        Returns:
            Queue key string
        """
        return f"{trading_pair}.diff"


