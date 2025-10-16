"""
WebSocket Connection Manager for Coins.xyz Exchange.

This module provides comprehensive WebSocket connection management with proper
lifecycle handling, reconnection logic, and subscription management.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable
import weakref

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
from hummingbot.connector.exchange.coinsxyz import coinsxyz_web_utils as web_utils
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class ConnectionState(Enum):
    """WebSocket connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class SubscriptionType(Enum):
    """WebSocket subscription types."""
    ORDER_BOOK = "depth"
    TRADES = "trade"
    TICKER = "ticker"
    KLINES = "kline"


class CoinsxyzWebSocketConnectionManager:
    """
    WebSocket connection manager for Coins.xyz exchange.

    Provides comprehensive connection lifecycle management including:
    - Automatic reconnection with exponential backoff
    - Subscription management for multiple data streams
    - Message routing and validation
    - Connection health monitoring
    - Graceful shutdown handling
    """

    def __init__(self,
                 api_factory: WebAssistantsFactory = None,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        """
        Initialize WebSocket connection manager.

        Args:
            api_factory: Web assistants factory for creating connections
            domain: API domain (default or testnet)
        """
        self._api_factory = api_factory or WebAssistantsFactory()
        self._domain = domain
        self._logger = None

        # Connection management
        self._ws_assistant: Optional[WSAssistant] = None
        self._connection_state = ConnectionState.DISCONNECTED
        self._connection_lock = asyncio.Lock()

        # Subscription management
        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        self._subscription_callbacks: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}
        self._subscription_id_counter = 1

        # Reconnection management
        self._reconnect_task: Optional[asyncio.Task] = None
        self._max_reconnect_attempts = 10
        self._reconnect_delay = 1.0  # Initial delay in seconds
        self._max_reconnect_delay = 60.0  # Maximum delay in seconds
        self._reconnect_attempts = 0

        # Health monitoring
        self._last_message_time = 0.0
        self._ping_task: Optional[asyncio.Task] = None
        self._ping_interval = CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL

        # Message processing
        self._message_listener_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        # Weak references to prevent circular references
        self._subscribers: Set[weakref.ReferenceType] = set()

    def logger(self) -> HummingbotLogger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connection_state == ConnectionState.CONNECTED

    @property
    def connection_state(self) -> ConnectionState:
        """Get current connection state."""
        return self._connection_state

    async def start(self) -> None:
        """
        Start the WebSocket connection manager.

        Initiates connection and starts background tasks for message processing
        and health monitoring.
        """
        if self._connection_state != ConnectionState.DISCONNECTED:
            self.logger().warning("Connection manager already started")
            return

        self.logger().info("Starting WebSocket connection manager")

        # Start connection
        await self._connect()

        # Start background tasks
        self._message_listener_task = asyncio.create_task(self._message_listener())
        self._ping_task = asyncio.create_task(self._ping_loop())

        self.logger().info("WebSocket connection manager started successfully")

    async def stop(self) -> None:
        """
        Stop the WebSocket connection manager.

        Gracefully shuts down all connections and background tasks.
        """
        self.logger().info("Stopping WebSocket connection manager")

        # Signal shutdown
        self._shutdown_event.set()

        # Cancel background tasks
        if self._message_listener_task:
            self._message_listener_task.cancel()
            try:
                await self._message_listener_task
            except asyncio.CancelledError:
                pass

        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        # Disconnect WebSocket
        await self._disconnect()

        # Clear subscriptions
        self._subscriptions.clear()
        self._subscription_callbacks.clear()

        self.logger().info("WebSocket connection manager stopped")

    async def _connect(self) -> None:
        """
        Establish WebSocket connection.

        Creates new WebSocket assistant and connects to the exchange.
        """
        async with self._connection_lock:
            if self._connection_state in [ConnectionState.CONNECTING, ConnectionState.CONNECTED]:
                return

            self._connection_state = ConnectionState.CONNECTING
            self.logger().info("Connecting to WebSocket...")

            try:
                # Create new WebSocket assistant
                self._ws_assistant = await self._api_factory.get_ws_assistant()

                # Connect to WebSocket
                ws_url = web_utils.websocket_url(self._domain)
                await self._ws_assistant.connect(
                    ws_url=ws_url,
                    ping_timeout=self._ping_interval,
                    message_timeout=self._ping_interval * 2
                )

                self._connection_state = ConnectionState.CONNECTED
                self._last_message_time = time.time()
                self._reconnect_attempts = 0

                self.logger().info(f"WebSocket connected successfully to {ws_url}")

                # Resubscribe to all active subscriptions
                await self._resubscribe_all()

            except Exception as e:
                self._connection_state = ConnectionState.FAILED
                self.logger().error(f"WebSocket connection failed: {e}")

                # Schedule reconnection
                if not self._shutdown_event.is_set():
                    await self._schedule_reconnect()

                raise

    async def _disconnect(self) -> None:
        """
        Disconnect WebSocket connection.

        Cleanly closes the WebSocket connection and resets state.
        """
        async with self._connection_lock:
            if self._ws_assistant:
                try:
                    await self._ws_assistant.disconnect()
                except Exception as e:
                    self.logger().warning(f"Error during WebSocket disconnect: {e}")
                finally:
                    self._ws_assistant = None

            self._connection_state = ConnectionState.DISCONNECTED
            self.logger().info("WebSocket disconnected")

    async def _schedule_reconnect(self) -> None:
        """
        Schedule reconnection with exponential backoff.

        Implements exponential backoff strategy for reconnection attempts.
        """
        if self._reconnect_task and not self._reconnect_task.done():
            return

        self._reconnect_attempts += 1

        if self._reconnect_attempts > self._max_reconnect_attempts:
            self.logger().error("Maximum reconnection attempts reached, giving up")
            self._connection_state = ConnectionState.FAILED
            return

        # Calculate delay with exponential backoff
        delay = min(
            self._reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
            self._max_reconnect_delay
        )

        self.logger().info(f"Scheduling reconnection attempt {self._reconnect_attempts} in {delay:.1f}s")

        self._reconnect_task = asyncio.create_task(self._reconnect_after_delay(delay))

    async def _reconnect_after_delay(self, delay: float) -> None:
        """
        Reconnect after specified delay.

        Args:
            delay: Delay in seconds before reconnection attempt
        """
        try:
            await asyncio.sleep(delay)

            if self._shutdown_event.is_set():
                return

            self._connection_state = ConnectionState.RECONNECTING
            self.logger().info("Attempting to reconnect...")

            await self._connect()

        except Exception as e:
            self.logger().error(f"Reconnection attempt failed: {e}")

            if not self._shutdown_event.is_set():
                await self._schedule_reconnect()

    async def _resubscribe_all(self) -> None:
        """
        Resubscribe to all active subscriptions.

        Called after successful reconnection to restore all subscriptions.
        """
        if not self._subscriptions:
            return

        self.logger().info(f"Resubscribing to {len(self._subscriptions)} subscriptions")

        for subscription_key, subscription_data in self._subscriptions.items():
            try:
                await self._send_subscription_request(
                    subscription_data["method"],
                    subscription_data["params"],
                    subscription_data["id"]
                )
                self.logger().debug(f"Resubscribed to {subscription_key}")
            except Exception as e:
                self.logger().error(f"Failed to resubscribe to {subscription_key}: {e}")

    async def _send_subscription_request(self, method: str, params: List[str], request_id: int) -> None:
        """
        Send subscription request to WebSocket.

        Args:
            method: Subscription method (SUBSCRIBE/UNSUBSCRIBE)
            params: Subscription parameters
            request_id: Request ID for tracking
        """
        if not self._ws_assistant or self._connection_state != ConnectionState.CONNECTED:
            raise RuntimeError("WebSocket not connected")

        request = WSJSONRequest({
            "method": method,
            "params": params,
            "id": request_id
        })

        await self._ws_assistant.send(request)
        self.logger().debug(f"Sent {method} request: {params}")

    async def _message_listener(self) -> None:
        """
        Listen for incoming WebSocket messages.

        Processes all incoming messages and routes them to appropriate handlers.
        """
        self.logger().info("Starting WebSocket message listener")

        while not self._shutdown_event.is_set():
            try:
                if not self._ws_assistant or self._connection_state != ConnectionState.CONNECTED:
                    await asyncio.sleep(1)
                    continue

                # Receive message with timeout
                try:
                    async for ws_response in self._ws_assistant.iter_messages():
                        if self._shutdown_event.is_set():
                            break

                        self._last_message_time = time.time()
                        await self._process_message(ws_response)

                except asyncio.TimeoutError:
                    self.logger().warning("WebSocket message timeout")
                    continue

            except Exception as e:
                self.logger().error(f"Error in message listener: {e}")

                if not self._shutdown_event.is_set():
                    await self._schedule_reconnect()

                await asyncio.sleep(1)

        self.logger().info("WebSocket message listener stopped")

    async def _process_message(self, ws_response: WSResponse) -> None:
        """
        Process incoming WebSocket message.

        Args:
            ws_response: WebSocket response containing message data
        """
        try:
            message_data = ws_response.data

            if not isinstance(message_data, dict):
                self.logger().warning(f"Received non-dict message: {message_data}")
                return

            # Route message to appropriate handlers
            stream = message_data.get("stream", "")
            if stream:
                await self._route_stream_message(stream, message_data)
            else:
                # Handle subscription responses and other control messages
                await self._handle_control_message(message_data)

        except Exception as e:
            self.logger().error(f"Error processing WebSocket message: {e}")

    async def _route_stream_message(self, stream: str, message_data: Dict[str, Any]) -> None:
        """
        Route stream message to registered callbacks.

        Args:
            stream: Stream identifier
            message_data: Message data
        """
        callbacks = self._subscription_callbacks.get(stream, [])

        if not callbacks:
            self.logger().debug(f"No callbacks registered for stream: {stream}")
            return

        # Execute all callbacks for this stream
        for callback in callbacks:
            try:
                await callback(message_data)
            except Exception as e:
                self.logger().error(f"Error in stream callback for {stream}: {e}")

    async def _handle_control_message(self, message_data: Dict[str, Any]) -> None:
        """
        Handle control messages (subscription responses, errors, etc.).

        Args:
            message_data: Control message data
        """
        message_id = message_data.get("id")
        result = message_data.get("result")
        error = message_data.get("error")

        if error:
            self.logger().error(f"WebSocket error (ID: {message_id}): {error}")
        elif result is not None:
            self.logger().debug(f"WebSocket response (ID: {message_id}): {result}")
        else:
            self.logger().debug(f"Unhandled control message: {message_data}")

    async def _ping_loop(self) -> None:
        """
        Ping loop for connection health monitoring.

        Monitors connection health and triggers reconnection if needed.
        """
        self.logger().info("Starting WebSocket ping loop")

        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._ping_interval)

                if self._shutdown_event.is_set():
                    break

                # Check if we've received messages recently
                time_since_last_message = time.time() - self._last_message_time

                if time_since_last_message > self._ping_interval * 2:
                    self.logger().warning(f"No messages received for {time_since_last_message:.1f}s, reconnecting")
                    await self._schedule_reconnect()

            except Exception as e:
                self.logger().error(f"Error in ping loop: {e}")

        self.logger().info("WebSocket ping loop stopped")

    # Subscription Management Methods

    async def subscribe_to_order_book(self,
                                      trading_pair: str,
                                      callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> str:
        """
        Subscribe to order book updates for a trading pair.

        Args:
            trading_pair: Trading pair in Hummingbot format (e.g., "BTC-USDT")
            callback: Callback function to handle order book updates

        Returns:
            Subscription key for managing the subscription
        """
        from hummingbot.connector.exchange.coinsxyz import coinsxyz_utils as utils

        symbol = utils.convert_to_exchange_trading_pair(trading_pair).lower()
        stream = f"{symbol}@depth"

        return await self._subscribe_to_stream(
            stream=stream,
            subscription_type=SubscriptionType.ORDER_BOOK,
            callback=callback
        )

    async def subscribe_to_trades(self,
                                  trading_pair: str,
                                  callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> str:
        """
        Subscribe to trade updates for a trading pair.

        Args:
            trading_pair: Trading pair in Hummingbot format
            callback: Callback function to handle trade updates

        Returns:
            Subscription key for managing the subscription
        """
        from hummingbot.connector.exchange.coinsxyz import coinsxyz_utils as utils

        symbol = utils.convert_to_exchange_trading_pair(trading_pair).lower()
        stream = f"{symbol}@trade"

        return await self._subscribe_to_stream(
            stream=stream,
            subscription_type=SubscriptionType.TRADES,
            callback=callback
        )

    async def subscribe_to_ticker(self,
                                  trading_pair: str,
                                  callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> str:
        """
        Subscribe to ticker updates for a trading pair.

        Args:
            trading_pair: Trading pair in Hummingbot format
            callback: Callback function to handle ticker updates

        Returns:
            Subscription key for managing the subscription
        """
        from hummingbot.connector.exchange.coinsxyz import coinsxyz_utils as utils

        symbol = utils.convert_to_exchange_trading_pair(trading_pair).lower()
        stream = f"{symbol}@ticker"

        return await self._subscribe_to_stream(
            stream=stream,
            subscription_type=SubscriptionType.TICKER,
            callback=callback
        )

    async def subscribe_to_klines(self,
                                  trading_pair: str,
                                  interval: str,
                                  callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> str:
        """
        Subscribe to klines/candlestick updates for a trading pair.

        Args:
            trading_pair: Trading pair in Hummingbot format
            interval: Kline interval (1m, 5m, 1h, etc.)
            callback: Callback function to handle kline updates

        Returns:
            Subscription key for managing the subscription
        """
        from hummingbot.connector.exchange.coinsxyz import coinsxyz_utils as utils

        symbol = utils.convert_to_exchange_trading_pair(trading_pair).lower()
        stream = f"{symbol}@kline_{interval}"

        return await self._subscribe_to_stream(
            stream=stream,
            subscription_type=SubscriptionType.KLINES,
            callback=callback
        )

    async def _subscribe_to_stream(self,
                                   stream: str,
                                   subscription_type: SubscriptionType,
                                   callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> str:
        """
        Subscribe to a WebSocket stream.

        Args:
            stream: Stream identifier
            subscription_type: Type of subscription
            callback: Callback function for handling messages

        Returns:
            Subscription key
        """
        subscription_key = f"{subscription_type.value}_{stream}"

        # Add callback to subscription callbacks
        if stream not in self._subscription_callbacks:
            self._subscription_callbacks[stream] = []
        self._subscription_callbacks[stream].append(callback)

        # Store subscription data
        subscription_id = self._subscription_id_counter
        self._subscription_id_counter += 1

        self._subscriptions[subscription_key] = {
            "method": "SUBSCRIBE",
            "params": [stream],
            "id": subscription_id,
            "stream": stream,
            "type": subscription_type,
            "callback": callback
        }

        # Send subscription request if connected
        if self._connection_state == ConnectionState.CONNECTED:
            try:
                await self._send_subscription_request("SUBSCRIBE", [stream], subscription_id)
                self.logger().info(f"Subscribed to {stream}")
            except Exception as e:
                self.logger().error(f"Failed to subscribe to {stream}: {e}")
                # Remove from subscriptions on failure
                del self._subscriptions[subscription_key]
                self._subscription_callbacks[stream].remove(callback)
                raise
        else:
            self.logger().info(f"Subscription to {stream} queued (not connected)")

        return subscription_key

    async def unsubscribe(self, subscription_key: str) -> None:
        """
        Unsubscribe from a WebSocket stream.

        Args:
            subscription_key: Subscription key returned from subscribe method
        """
        if subscription_key not in self._subscriptions:
            self.logger().warning(f"Subscription key not found: {subscription_key}")
            return

        subscription_data = self._subscriptions[subscription_key]
        stream = subscription_data["stream"]
        callback = subscription_data["callback"]

        # Remove callback
        if stream in self._subscription_callbacks:
            try:
                self._subscription_callbacks[stream].remove(callback)
                if not self._subscription_callbacks[stream]:
                    del self._subscription_callbacks[stream]
            except ValueError:
                pass

        # Send unsubscribe request if connected
        if self._connection_state == ConnectionState.CONNECTED:
            try:
                subscription_id = self._subscription_id_counter
                self._subscription_id_counter += 1

                await self._send_subscription_request("UNSUBSCRIBE", [stream], subscription_id)
                self.logger().info(f"Unsubscribed from {stream}")
            except Exception as e:
                self.logger().error(f"Failed to unsubscribe from {stream}: {e}")

        # Remove subscription
        del self._subscriptions[subscription_key]

    async def unsubscribe_all(self) -> None:
        """
        Unsubscribe from all WebSocket streams.
        """
        subscription_keys = list(self._subscriptions.keys())

        for subscription_key in subscription_keys:
            try:
                await self.unsubscribe(subscription_key)
            except Exception as e:
                self.logger().error(f"Error unsubscribing from {subscription_key}: {e}")

        self.logger().info("Unsubscribed from all streams")

    def get_active_subscriptions(self) -> List[str]:
        """
        Get list of active subscription keys.

        Returns:
            List of active subscription keys
        """
        return list(self._subscriptions.keys())

    def get_subscription_count(self) -> int:
        """
        Get number of active subscriptions.

        Returns:
            Number of active subscriptions
        """
        return len(self._subscriptions)

    async def connect(self) -> None:
        """
        Connect to WebSocket - Day 16 Implementation.

        Public method to establish WebSocket connection.
        This is an alias for the internal _connect method.
        """
        await self._connect()

    async def disconnect(self) -> None:
        """
        Disconnect from WebSocket - Day 16 Implementation.

        Public method to disconnect WebSocket connection.
        This is an alias for the internal _disconnect method.
        """
        await self._disconnect()

    async def _handle_user_stream_message(self, message_data: Dict[str, Any]) -> None:
        """
        Handle user stream messages - Day 16 Implementation.

        Processes user-specific messages like balance updates, order updates,
        and trade executions from the user data stream.

        Args:
            message_data: User stream message data
        """
        try:
            # Check if this is a user stream message
            if 'stream' in message_data and 'data' in message_data:
                message_data['stream']
                data = message_data['data']

                # Route user stream messages to appropriate handlers
                if 'outboundAccountPosition' in data:
                    # Balance update
                    await self._handle_balance_update(data)
                elif 'executionReport' in data:
                    # Order update
                    await self._handle_order_update(data)
                elif 'trade' in data:
                    # Trade execution
                    await self._handle_trade_update(data)
                else:
                    self.logger().debug(f"Unhandled user stream message type: {data}")

            # Route to registered callbacks
            await self._route_stream_message("user_stream", message_data)

        except Exception as e:
            self.logger().error(f"Error handling user stream message: {e}")

    async def _handle_balance_update(self, data: Dict[str, Any]) -> None:
        """Handle balance update from user stream."""
        try:
            self.logger().debug(f"Processing balance update: {data}")
            # Balance update processing would be implemented here
        except Exception as e:
            self.logger().error(f"Error processing balance update: {e}")

    async def _handle_order_update(self, data: Dict[str, Any]) -> None:
        """Handle order update from user stream."""
        try:
            self.logger().debug(f"Processing order update: {data}")
            # Order update processing would be implemented here
        except Exception as e:
            self.logger().error(f"Error processing order update: {e}")

    async def _handle_trade_update(self, data: Dict[str, Any]) -> None:
        """Handle trade update from user stream."""
        try:
            self.logger().debug(f"Processing trade update: {data}")
            # Trade update processing would be implemented here
        except Exception as e:
            self.logger().error(f"Error processing trade update: {e}")
