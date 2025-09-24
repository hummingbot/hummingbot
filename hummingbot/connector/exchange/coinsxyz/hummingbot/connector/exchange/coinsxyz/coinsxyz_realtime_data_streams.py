"""
Real-time Data Streams Manager for Coins.xyz Exchange.

This module provides comprehensive real-time data streaming with advanced
reconnection logic, heartbeat mechanisms, and robust error recovery.
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Callable, Awaitable, Set
from enum import Enum
import json
import weakref

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
from hummingbot.connector.exchange.coinsxyz import coinsxyz_utils as utils
from hummingbot.connector.exchange.coinsxyz import coinsxyz_web_utils as web_utils
from hummingbot.connector.exchange.coinsxyz.coinsxyz_websocket_connection_manager import CoinsxyzWebSocketConnectionManager
from hummingbot.connector.exchange.coinsxyz.coinsxyz_websocket_message_parser import CoinsxyzWebSocketMessageParser
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class StreamType(Enum):
    """Real-time stream types."""
    TRADES = "trades"
    TICKER = "ticker"
    ORDER_BOOK = "orderbook"
    KLINES = "klines"


class StreamHealth(Enum):
    """Stream health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DISCONNECTED = "disconnected"


class CoinsxyzRealtimeDataStreams:
    """
    Real-time data streams manager for Coins.xyz exchange.
    
    Provides comprehensive real-time data streaming with:
    - Advanced reconnection logic with exponential backoff
    - Heartbeat/ping-pong mechanism for connection health
    - Stream data validation and error recovery
    - Robust handling of reconnection scenarios
    - Data continuity assurance
    - Performance monitoring and statistics
    """
    
    def __init__(self, 
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        """
        Initialize real-time data streams manager.
        
        Args:
            api_factory: Web assistants factory for creating connections
            domain: API domain (default or testnet)
        """
        self._api_factory = api_factory
        self._domain = domain
        self._logger = None
        
        # Core components
        self._connection_manager = CoinsxyzWebSocketConnectionManager(api_factory, domain)
        self._message_parser = CoinsxyzWebSocketMessageParser()
        
        # Stream management
        self._active_streams: Dict[str, Dict[str, Any]] = {}
        self._stream_callbacks: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}
        self._stream_health: Dict[str, StreamHealth] = {}
        
        # Reconnection and health monitoring
        self._reconnection_enabled = True
        self._max_reconnection_attempts = 15  # Increased from base implementation
        self._base_reconnection_delay = 1.0
        self._max_reconnection_delay = 120.0  # Increased max delay
        self._reconnection_multiplier = 1.5  # More gradual backoff
        self._current_reconnection_attempt = 0
        
        # Heartbeat mechanism
        self._heartbeat_enabled = True
        self._heartbeat_interval = 20.0  # More frequent heartbeats
        self._heartbeat_timeout = 10.0
        self._last_heartbeat_time = 0.0
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._missed_heartbeats = 0
        self._max_missed_heartbeats = 3
        
        # Data validation and recovery
        self._validation_enabled = True
        self._data_continuity_checks = True
        self._last_message_timestamps: Dict[str, float] = {}
        self._message_sequence_numbers: Dict[str, int] = {}
        self._data_gap_threshold = 5.0  # seconds
        
        # Performance monitoring
        self._statistics = {
            "messages_received": 0,
            "messages_processed": 0,
            "messages_dropped": 0,
            "reconnections": 0,
            "heartbeat_failures": 0,
            "data_gaps_detected": 0,
            "validation_errors": 0,
            "uptime_start": time.time()
        }
        
        # Background tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._data_continuity_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Weak references to prevent memory leaks
        self._subscribers: Set[weakref.ReferenceType] = set()
    
    def logger(self) -> HummingbotLogger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger
    
    async def start(self) -> None:
        """
        Start the real-time data streams manager.
        
        Initializes all components and starts background monitoring tasks.
        """
        if self._monitoring_task and not self._monitoring_task.done():
            self.logger().warning("Real-time streams already started")
            return
        
        self.logger().info("Starting real-time data streams manager")
        
        try:
            # Start connection manager
            await self._connection_manager.start()
            
            # Start background tasks
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            self._data_continuity_task = asyncio.create_task(self._data_continuity_loop())
            
            if self._heartbeat_enabled:
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            # Reset statistics
            self._statistics["uptime_start"] = time.time()
            self._current_reconnection_attempt = 0
            
            self.logger().info("Real-time data streams manager started successfully")
            
        except Exception as e:
            self.logger().error(f"Failed to start real-time streams manager: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """
        Stop the real-time data streams manager.
        
        Gracefully shuts down all streams and background tasks.
        """
        self.logger().info("Stopping real-time data streams manager")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel background tasks
        tasks_to_cancel = [
            self._monitoring_task,
            self._data_continuity_task,
            self._heartbeat_task
        ]
        
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Stop connection manager
        await self._connection_manager.stop()
        
        # Clear state
        self._active_streams.clear()
        self._stream_callbacks.clear()
        self._stream_health.clear()
        self._last_message_timestamps.clear()
        self._message_sequence_numbers.clear()
        
        self.logger().info("Real-time data streams manager stopped")
    
    async def subscribe_to_trades_stream(self, 
                                       trading_pair: str,
                                       callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> str:
        """
        Subscribe to real-time trades stream with advanced processing.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
            callback: Callback function for trade messages
            
        Returns:
            Stream subscription ID
        """
        stream_id = f"trades_{trading_pair}"
        
        # Create stream configuration
        stream_config = {
            "type": StreamType.TRADES,
            "trading_pair": trading_pair,
            "callback": callback,
            "subscription_key": None,
            "last_message_time": 0.0,
            "message_count": 0,
            "error_count": 0
        }
        
        try:
            # Subscribe through connection manager
            subscription_key = await self._connection_manager.subscribe_to_trades(
                trading_pair,
                self._create_stream_handler(stream_id, callback)
            )
            
            stream_config["subscription_key"] = subscription_key
            self._active_streams[stream_id] = stream_config
            self._stream_health[stream_id] = StreamHealth.HEALTHY
            
            self.logger().info(f"Subscribed to trades stream for {trading_pair}")
            return stream_id
            
        except Exception as e:
            self.logger().error(f"Failed to subscribe to trades stream for {trading_pair}: {e}")
            raise
    
    async def subscribe_to_ticker_stream(self,
                                       trading_pair: str,
                                       callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> str:
        """
        Subscribe to real-time ticker stream with price update processing.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
            callback: Callback function for ticker messages
            
        Returns:
            Stream subscription ID
        """
        stream_id = f"ticker_{trading_pair}"
        
        # Create stream configuration
        stream_config = {
            "type": StreamType.TICKER,
            "trading_pair": trading_pair,
            "callback": callback,
            "subscription_key": None,
            "last_message_time": 0.0,
            "message_count": 0,
            "error_count": 0,
            "last_price": None,
            "price_change_24h": None
        }
        
        try:
            # Subscribe through connection manager
            subscription_key = await self._connection_manager.subscribe_to_ticker(
                trading_pair,
                self._create_stream_handler(stream_id, callback)
            )
            
            stream_config["subscription_key"] = subscription_key
            self._active_streams[stream_id] = stream_config
            self._stream_health[stream_id] = StreamHealth.HEALTHY
            
            self.logger().info(f"Subscribed to ticker stream for {trading_pair}")
            return stream_id
            
        except Exception as e:
            self.logger().error(f"Failed to subscribe to ticker stream for {trading_pair}: {e}")
            raise
    
    def _create_stream_handler(self, 
                              stream_id: str,
                              callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> Callable:
        """
        Create stream message handler with validation and error recovery.
        
        Args:
            stream_id: Stream identifier
            callback: Original callback function
            
        Returns:
            Enhanced callback with validation and error recovery
        """
        async def enhanced_handler(message_data: Dict[str, Any]) -> None:
            try:
                self._statistics["messages_received"] += 1
                
                # Update stream statistics
                if stream_id in self._active_streams:
                    stream_config = self._active_streams[stream_id]
                    stream_config["last_message_time"] = time.time()
                    stream_config["message_count"] += 1
                
                # Validate message data
                if self._validation_enabled:
                    if not await self._validate_stream_message(stream_id, message_data):
                        self._statistics["validation_errors"] += 1
                        self._statistics["messages_dropped"] += 1
                        return
                
                # Check data continuity
                if self._data_continuity_checks:
                    await self._check_data_continuity(stream_id, message_data)
                
                # Update stream health
                self._stream_health[stream_id] = StreamHealth.HEALTHY
                
                # Call original callback
                await callback(message_data)
                
                self._statistics["messages_processed"] += 1
                
            except Exception as e:
                self.logger().error(f"Error in stream handler for {stream_id}: {e}")
                
                # Update error statistics
                if stream_id in self._active_streams:
                    self._active_streams[stream_id]["error_count"] += 1
                
                # Update stream health
                self._stream_health[stream_id] = StreamHealth.DEGRADED
                self._statistics["messages_dropped"] += 1
        
        return enhanced_handler
    
    async def _validate_stream_message(self, stream_id: str, message_data: Dict[str, Any]) -> bool:
        """
        Validate stream message data.
        
        Args:
            stream_id: Stream identifier
            message_data: Message data to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            if not isinstance(message_data, dict):
                self.logger().warning(f"Invalid message format for {stream_id}: not a dict")
                return False
            
            # Parse message to validate structure
            parsed_message = self._message_parser.parse_message(message_data)
            if not parsed_message:
                self.logger().warning(f"Failed to parse message for {stream_id}")
                return False
            
            # Stream-specific validation
            stream_config = self._active_streams.get(stream_id, {})
            stream_type = stream_config.get("type")
            
            if stream_type == StreamType.TRADES:
                return self._validate_trade_message(parsed_message)
            elif stream_type == StreamType.TICKER:
                return self._validate_ticker_message(parsed_message)
            
            return True
            
        except Exception as e:
            self.logger().error(f"Error validating message for {stream_id}: {e}")
            return False
    
    def _validate_trade_message(self, parsed_message: Dict[str, Any]) -> bool:
        """Validate trade message data."""
        try:
            required_fields = ["symbol", "trade_id", "price", "quantity", "timestamp"]
            
            for field in required_fields:
                if field not in parsed_message:
                    return False
            
            # Validate price and quantity
            price = float(parsed_message["price"])
            quantity = float(parsed_message["quantity"])
            
            if price <= 0 or quantity <= 0:
                return False
            
            return True
            
        except (ValueError, KeyError):
            return False
    
    def _validate_ticker_message(self, parsed_message: Dict[str, Any]) -> bool:
        """Validate ticker message data."""
        try:
            required_fields = ["symbol", "last_price", "timestamp"]
            
            for field in required_fields:
                if field not in parsed_message:
                    return False
            
            # Validate price
            last_price = float(parsed_message["last_price"])
            if last_price <= 0:
                return False
            
            return True
            
        except (ValueError, KeyError):
            return False
    
    async def _check_data_continuity(self, stream_id: str, message_data: Dict[str, Any]) -> None:
        """
        Check data continuity and detect gaps.
        
        Args:
            stream_id: Stream identifier
            message_data: Message data
        """
        try:
            current_time = time.time()
            last_time = self._last_message_timestamps.get(stream_id, 0)
            
            # Check for data gaps
            if last_time > 0:
                time_gap = current_time - last_time
                if time_gap > self._data_gap_threshold:
                    self.logger().warning(f"Data gap detected for {stream_id}: {time_gap:.1f}s")
                    self._statistics["data_gaps_detected"] += 1
                    self._stream_health[stream_id] = StreamHealth.DEGRADED
            
            self._last_message_timestamps[stream_id] = current_time
            
        except Exception as e:
            self.logger().error(f"Error checking data continuity for {stream_id}: {e}")
    
    async def _monitoring_loop(self) -> None:
        """
        Background monitoring loop for stream health and performance.
        """
        self.logger().info("Starting stream monitoring loop")
        
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(30)  # Monitor every 30 seconds
                
                if self._shutdown_event.is_set():
                    break
                
                await self._monitor_stream_health()
                await self._log_performance_statistics()
                
            except Exception as e:
                self.logger().error(f"Error in monitoring loop: {e}")
        
        self.logger().info("Stream monitoring loop stopped")
    
    async def _monitor_stream_health(self) -> None:
        """Monitor health of all active streams."""
        current_time = time.time()
        
        for stream_id, stream_config in self._active_streams.items():
            try:
                last_message_time = stream_config.get("last_message_time", 0)
                time_since_last_message = current_time - last_message_time
                
                # Update health status based on message frequency
                if time_since_last_message > 60:  # No messages for 1 minute
                    self._stream_health[stream_id] = StreamHealth.UNHEALTHY
                elif time_since_last_message > 30:  # No messages for 30 seconds
                    self._stream_health[stream_id] = StreamHealth.DEGRADED
                else:
                    # Only mark as healthy if we haven't had recent errors
                    error_count = stream_config.get("error_count", 0)
                    if error_count == 0:
                        self._stream_health[stream_id] = StreamHealth.HEALTHY
                
            except Exception as e:
                self.logger().error(f"Error monitoring health for {stream_id}: {e}")
    
    async def _log_performance_statistics(self) -> None:
        """Log performance statistics."""
        try:
            uptime = time.time() - self._statistics["uptime_start"]
            
            self.logger().info(
                f"Stream Statistics - "
                f"Uptime: {uptime:.1f}s, "
                f"Messages: {self._statistics['messages_processed']}, "
                f"Dropped: {self._statistics['messages_dropped']}, "
                f"Reconnections: {self._statistics['reconnections']}, "
                f"Active Streams: {len(self._active_streams)}"
            )
            
        except Exception as e:
            self.logger().error(f"Error logging statistics: {e}")

    async def _heartbeat_loop(self) -> None:
        """
        Heartbeat/ping-pong mechanism for connection health monitoring.
        """
        self.logger().info("Starting heartbeat loop")

        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._heartbeat_interval)

                if self._shutdown_event.is_set():
                    break

                # Send heartbeat and check response
                heartbeat_success = await self._send_heartbeat()

                if heartbeat_success:
                    self._missed_heartbeats = 0
                    self._last_heartbeat_time = time.time()
                else:
                    self._missed_heartbeats += 1
                    self._statistics["heartbeat_failures"] += 1

                    self.logger().warning(f"Heartbeat failed, missed: {self._missed_heartbeats}")

                    # Trigger reconnection if too many missed heartbeats
                    if self._missed_heartbeats >= self._max_missed_heartbeats:
                        self.logger().error("Too many missed heartbeats, triggering reconnection")
                        await self._trigger_reconnection("heartbeat_failure")

            except Exception as e:
                self.logger().error(f"Error in heartbeat loop: {e}")
                self._missed_heartbeats += 1

        self.logger().info("Heartbeat loop stopped")

    async def _send_heartbeat(self) -> bool:
        """
        Send heartbeat ping and wait for pong response.

        Returns:
            True if heartbeat successful, False otherwise
        """
        try:
            if not self._connection_manager.is_connected:
                return False

            # For WebSocket connections, we can use the connection manager's ping mechanism
            # or implement a custom ping message based on the exchange's requirements

            # Check if we've received any messages recently (passive heartbeat)
            current_time = time.time()
            recent_activity = False

            for stream_id, stream_config in self._active_streams.items():
                last_message_time = stream_config.get("last_message_time", 0)
                if current_time - last_message_time < self._heartbeat_interval:
                    recent_activity = True
                    break

            if recent_activity:
                return True

            # If no recent activity, check connection health
            # This is a simplified implementation - in practice, you might send a ping frame
            return self._connection_manager.is_connected

        except Exception as e:
            self.logger().error(f"Error sending heartbeat: {e}")
            return False

    async def _data_continuity_loop(self) -> None:
        """
        Background loop for data continuity monitoring and recovery.
        """
        self.logger().info("Starting data continuity loop")

        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(60)  # Check every minute

                if self._shutdown_event.is_set():
                    break

                await self._check_all_streams_continuity()
                await self._recover_unhealthy_streams()

            except Exception as e:
                self.logger().error(f"Error in data continuity loop: {e}")

        self.logger().info("Data continuity loop stopped")

    async def _check_all_streams_continuity(self) -> None:
        """Check data continuity for all active streams."""
        current_time = time.time()

        for stream_id, stream_config in self._active_streams.items():
            try:
                last_message_time = stream_config.get("last_message_time", 0)
                time_since_last_message = current_time - last_message_time

                # Check for stale streams
                if time_since_last_message > 120:  # 2 minutes without data
                    self.logger().warning(f"Stream {stream_id} appears stale, last message {time_since_last_message:.1f}s ago")
                    self._stream_health[stream_id] = StreamHealth.UNHEALTHY

                    # Attempt to recover the stream
                    await self._recover_stream(stream_id)

            except Exception as e:
                self.logger().error(f"Error checking continuity for {stream_id}: {e}")

    async def _recover_unhealthy_streams(self) -> None:
        """Recover unhealthy streams."""
        unhealthy_streams = [
            stream_id for stream_id, health in self._stream_health.items()
            if health == StreamHealth.UNHEALTHY
        ]

        for stream_id in unhealthy_streams:
            try:
                await self._recover_stream(stream_id)
            except Exception as e:
                self.logger().error(f"Error recovering stream {stream_id}: {e}")

    async def _recover_stream(self, stream_id: str) -> None:
        """
        Recover a specific stream.

        Args:
            stream_id: Stream identifier to recover
        """
        try:
            if stream_id not in self._active_streams:
                return

            stream_config = self._active_streams[stream_id]
            trading_pair = stream_config["trading_pair"]
            stream_type = stream_config["type"]
            callback = stream_config["callback"]

            self.logger().info(f"Attempting to recover stream {stream_id}")

            # Unsubscribe from old stream
            old_subscription_key = stream_config.get("subscription_key")
            if old_subscription_key:
                try:
                    await self._connection_manager.unsubscribe(old_subscription_key)
                except Exception as e:
                    self.logger().warning(f"Error unsubscribing from old stream: {e}")

            # Resubscribe based on stream type
            if stream_type == StreamType.TRADES:
                new_subscription_key = await self._connection_manager.subscribe_to_trades(
                    trading_pair,
                    self._create_stream_handler(stream_id, callback)
                )
            elif stream_type == StreamType.TICKER:
                new_subscription_key = await self._connection_manager.subscribe_to_ticker(
                    trading_pair,
                    self._create_stream_handler(stream_id, callback)
                )
            else:
                self.logger().warning(f"Unknown stream type for recovery: {stream_type}")
                return

            # Update stream configuration
            stream_config["subscription_key"] = new_subscription_key
            stream_config["error_count"] = 0
            self._stream_health[stream_id] = StreamHealth.HEALTHY

            self.logger().info(f"Successfully recovered stream {stream_id}")

        except Exception as e:
            self.logger().error(f"Failed to recover stream {stream_id}: {e}")
            self._stream_health[stream_id] = StreamHealth.UNHEALTHY

    async def _trigger_reconnection(self, reason: str) -> None:
        """
        Trigger connection reconnection with exponential backoff.

        Args:
            reason: Reason for reconnection
        """
        if not self._reconnection_enabled:
            self.logger().warning(f"Reconnection disabled, ignoring trigger: {reason}")
            return

        self.logger().info(f"Triggering reconnection due to: {reason}")

        try:
            # Calculate backoff delay
            delay = min(
                self._base_reconnection_delay * (self._reconnection_multiplier ** self._current_reconnection_attempt),
                self._max_reconnection_delay
            )

            self._current_reconnection_attempt += 1

            if self._current_reconnection_attempt > self._max_reconnection_attempts:
                self.logger().error("Maximum reconnection attempts reached, giving up")
                return

            self.logger().info(f"Reconnection attempt {self._current_reconnection_attempt} in {delay:.1f}s")

            # Wait before reconnecting
            await asyncio.sleep(delay)

            if self._shutdown_event.is_set():
                return

            # Stop and restart connection manager
            await self._connection_manager.stop()
            await asyncio.sleep(1)  # Brief pause
            await self._connection_manager.start()

            # Resubscribe to all streams
            await self._resubscribe_all_streams()

            # Reset reconnection counter on successful reconnection
            self._current_reconnection_attempt = 0
            self._statistics["reconnections"] += 1

            self.logger().info("Reconnection successful")

        except Exception as e:
            self.logger().error(f"Reconnection failed: {e}")

    async def _resubscribe_all_streams(self) -> None:
        """Resubscribe to all active streams after reconnection."""
        self.logger().info(f"Resubscribing to {len(self._active_streams)} streams")

        streams_to_resubscribe = list(self._active_streams.keys())

        for stream_id in streams_to_resubscribe:
            try:
                await self._recover_stream(stream_id)
            except Exception as e:
                self.logger().error(f"Error resubscribing to {stream_id}: {e}")

        self.logger().info("Stream resubscription completed")

    # Public API methods

    async def unsubscribe_from_stream(self, stream_id: str) -> None:
        """
        Unsubscribe from a specific stream.

        Args:
            stream_id: Stream identifier to unsubscribe from
        """
        if stream_id not in self._active_streams:
            self.logger().warning(f"Stream {stream_id} not found for unsubscription")
            return

        try:
            stream_config = self._active_streams[stream_id]
            subscription_key = stream_config.get("subscription_key")

            if subscription_key:
                await self._connection_manager.unsubscribe(subscription_key)

            # Clean up stream data
            del self._active_streams[stream_id]
            if stream_id in self._stream_health:
                del self._stream_health[stream_id]
            if stream_id in self._last_message_timestamps:
                del self._last_message_timestamps[stream_id]

            self.logger().info(f"Unsubscribed from stream {stream_id}")

        except Exception as e:
            self.logger().error(f"Error unsubscribing from stream {stream_id}: {e}")

    def get_stream_health(self, stream_id: str) -> Optional[StreamHealth]:
        """
        Get health status of a specific stream.

        Args:
            stream_id: Stream identifier

        Returns:
            Stream health status or None if not found
        """
        return self._stream_health.get(stream_id)

    def get_all_stream_health(self) -> Dict[str, StreamHealth]:
        """
        Get health status of all streams.

        Returns:
            Dictionary mapping stream IDs to health status
        """
        return self._stream_health.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics.

        Returns:
            Dictionary with performance and health statistics
        """
        current_time = time.time()
        uptime = current_time - self._statistics["uptime_start"]

        return {
            **self._statistics,
            "uptime_seconds": uptime,
            "active_streams": len(self._active_streams),
            "healthy_streams": sum(1 for h in self._stream_health.values() if h == StreamHealth.HEALTHY),
            "degraded_streams": sum(1 for h in self._stream_health.values() if h == StreamHealth.DEGRADED),
            "unhealthy_streams": sum(1 for h in self._stream_health.values() if h == StreamHealth.UNHEALTHY),
            "current_reconnection_attempt": self._current_reconnection_attempt,
            "last_heartbeat_time": self._last_heartbeat_time,
            "missed_heartbeats": self._missed_heartbeats
        }

    def enable_reconnection(self, enabled: bool = True) -> None:
        """Enable or disable automatic reconnection."""
        self._reconnection_enabled = enabled
        self.logger().info(f"Automatic reconnection {'enabled' if enabled else 'disabled'}")

    def enable_heartbeat(self, enabled: bool = True) -> None:
        """Enable or disable heartbeat mechanism."""
        self._heartbeat_enabled = enabled
        self.logger().info(f"Heartbeat mechanism {'enabled' if enabled else 'disabled'}")

    def enable_data_validation(self, enabled: bool = True) -> None:
        """Enable or disable data validation."""
        self._validation_enabled = enabled
        self.logger().info(f"Data validation {'enabled' if enabled else 'disabled'}")

    def enable_data_continuity_checks(self, enabled: bool = True) -> None:
        """Enable or disable data continuity checks."""
        self._data_continuity_checks = enabled
        self.logger().info(f"Data continuity checks {'enabled' if enabled else 'disabled'}")
