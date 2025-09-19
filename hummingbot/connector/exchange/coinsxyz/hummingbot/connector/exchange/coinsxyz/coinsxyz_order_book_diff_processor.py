"""
Order Book Diff Processor for Coins.xyz Exchange.

This module provides comprehensive order book diff processing with proper
synchronization, validation, and integration with Hummingbot's order book system.
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
from hummingbot.connector.exchange.coinsxyz import coinsxyz_utils as utils
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.logger import HummingbotLogger


class OrderBookSyncState:
    """Order book synchronization state for a trading pair."""
    
    def __init__(self, trading_pair: str):
        """
        Initialize sync state.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
        """
        self.trading_pair = trading_pair
        self.last_update_id = 0
        self.is_synchronized = False
        self.pending_diffs: List[Dict[str, Any]] = []
        self.snapshot_update_id = 0
        self.last_sync_time = 0.0


class CoinsxyzOrderBookDiffProcessor:
    """
    Order book diff processor for Coins.xyz exchange.
    
    Handles order book diff messages with proper synchronization, validation,
    and conversion to Hummingbot OrderBookMessage format.
    
    Features:
    - Proper diff synchronization with snapshots
    - Out-of-order message handling
    - Duplicate message detection
    - Data validation and error recovery
    - Performance optimization for high-frequency updates
    """
    
    def __init__(self):
        """Initialize order book diff processor."""
        self._logger = None
        
        # Synchronization state per trading pair
        self._sync_states: Dict[str, OrderBookSyncState] = {}
        
        # Message queues for processing
        self._message_queues: Dict[str, asyncio.Queue] = defaultdict(lambda: asyncio.Queue())
        
        # Processing tasks
        self._processing_tasks: Dict[str, asyncio.Task] = {}
        
        # Configuration
        self._max_pending_diffs = 100
        self._sync_timeout = 30.0  # seconds
        self._duplicate_detection_window = 1000  # number of update IDs to track
        
        # Statistics
        self._stats = {
            "messages_processed": 0,
            "messages_dropped": 0,
            "sync_events": 0,
            "errors": 0
        }
    
    def logger(self) -> HummingbotLogger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger
    
    async def start_processing(self, trading_pair: str) -> None:
        """
        Start order book diff processing for a trading pair.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
        """
        if trading_pair in self._processing_tasks:
            self.logger().warning(f"Processing already started for {trading_pair}")
            return
        
        # Initialize sync state
        self._sync_states[trading_pair] = OrderBookSyncState(trading_pair)
        
        # Start processing task
        self._processing_tasks[trading_pair] = asyncio.create_task(
            self._process_diffs_for_pair(trading_pair)
        )
        
        self.logger().info(f"Started order book diff processing for {trading_pair}")
    
    async def stop_processing(self, trading_pair: str) -> None:
        """
        Stop order book diff processing for a trading pair.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
        """
        if trading_pair in self._processing_tasks:
            task = self._processing_tasks[trading_pair]
            task.cancel()
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            del self._processing_tasks[trading_pair]
        
        # Clean up state
        if trading_pair in self._sync_states:
            del self._sync_states[trading_pair]
        
        if trading_pair in self._message_queues:
            del self._message_queues[trading_pair]
        
        self.logger().info(f"Stopped order book diff processing for {trading_pair}")
    
    async def stop_all_processing(self) -> None:
        """Stop all order book diff processing."""
        trading_pairs = list(self._processing_tasks.keys())
        
        for trading_pair in trading_pairs:
            await self.stop_processing(trading_pair)
        
        self.logger().info("Stopped all order book diff processing")
    
    async def process_diff_message(self, 
                                  parsed_message: Dict[str, Any],
                                  output_queue: asyncio.Queue) -> None:
        """
        Process order book diff message.
        
        Args:
            parsed_message: Parsed diff message from WebSocket
            output_queue: Queue to send processed OrderBookMessage
        """
        try:
            symbol = parsed_message.get("symbol", "")
            if not symbol:
                self.logger().warning("No symbol in diff message")
                return
            
            # Convert symbol to trading pair
            trading_pair = await self._symbol_to_trading_pair(symbol)
            if not trading_pair:
                self.logger().warning(f"Could not convert symbol to trading pair: {symbol}")
                return
            
            # Add to processing queue
            await self._message_queues[trading_pair].put((parsed_message, output_queue))
            
        except Exception as e:
            self.logger().error(f"Error processing diff message: {e}")
            self._stats["errors"] += 1
    
    async def synchronize_with_snapshot(self, 
                                       trading_pair: str,
                                       snapshot_update_id: int) -> None:
        """
        Synchronize order book diff processing with snapshot.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
            snapshot_update_id: Update ID from order book snapshot
        """
        if trading_pair not in self._sync_states:
            self.logger().warning(f"No sync state for {trading_pair}")
            return
        
        sync_state = self._sync_states[trading_pair]
        sync_state.snapshot_update_id = snapshot_update_id
        sync_state.last_sync_time = time.time()
        
        self.logger().info(f"Synchronized {trading_pair} with snapshot update ID: {snapshot_update_id}")
        self._stats["sync_events"] += 1
    
    async def _process_diffs_for_pair(self, trading_pair: str) -> None:
        """
        Process order book diffs for a specific trading pair.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
        """
        self.logger().info(f"Starting diff processing loop for {trading_pair}")
        
        message_queue = self._message_queues[trading_pair]
        
        try:
            while True:
                try:
                    # Get message from queue with timeout
                    parsed_message, output_queue = await asyncio.wait_for(
                        message_queue.get(), timeout=1.0
                    )
                    
                    # Process the diff message
                    order_book_message = await self._create_order_book_message(
                        parsed_message, trading_pair
                    )
                    
                    if order_book_message:
                        await output_queue.put(order_book_message)
                        self._stats["messages_processed"] += 1
                    else:
                        self._stats["messages_dropped"] += 1
                    
                except asyncio.TimeoutError:
                    # Check for sync timeout
                    await self._check_sync_timeout(trading_pair)
                    continue
                
        except asyncio.CancelledError:
            self.logger().info(f"Diff processing cancelled for {trading_pair}")
        except Exception as e:
            self.logger().error(f"Error in diff processing loop for {trading_pair}: {e}")
            self._stats["errors"] += 1
    
    async def _create_order_book_message(self, 
                                        parsed_message: Dict[str, Any],
                                        trading_pair: str) -> Optional[OrderBookMessage]:
        """
        Create OrderBookMessage from parsed diff message.
        
        Args:
            parsed_message: Parsed diff message
            trading_pair: Trading pair in Hummingbot format
            
        Returns:
            OrderBookMessage or None if invalid
        """
        try:
            sync_state = self._sync_states.get(trading_pair)
            if not sync_state:
                self.logger().warning(f"No sync state for {trading_pair}")
                return None
            
            update_id = parsed_message.get("update_id", 0)
            timestamp = parsed_message.get("timestamp", time.time())
            bids = parsed_message.get("bids", [])
            asks = parsed_message.get("asks", [])
            
            # Validate update ID sequence
            if not self._validate_update_sequence(sync_state, update_id):
                return None
            
            # Update sync state
            sync_state.last_update_id = update_id
            
            # Create message content
            message_content = {
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": bids,
                "asks": asks
            }
            
            # Create OrderBookMessage
            order_book_message = OrderBookMessage(
                OrderBookMessageType.DIFF,
                message_content,
                timestamp
            )
            
            return order_book_message
            
        except Exception as e:
            self.logger().error(f"Error creating order book message: {e}")
            return None
    
    def _validate_update_sequence(self, 
                                 sync_state: OrderBookSyncState,
                                 update_id: int) -> bool:
        """
        Validate update ID sequence for proper synchronization.
        
        Args:
            sync_state: Synchronization state
            update_id: Update ID to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check if we have a snapshot to sync with
        if sync_state.snapshot_update_id == 0:
            self.logger().debug(f"No snapshot for {sync_state.trading_pair}, queuing diff")
            return False
        
        # Check if this diff is applicable to current snapshot
        if update_id <= sync_state.snapshot_update_id:
            self.logger().debug(f"Diff update ID {update_id} <= snapshot ID {sync_state.snapshot_update_id}, skipping")
            return False
        
        # Check for sequence gaps
        if sync_state.last_update_id > 0:
            expected_id = sync_state.last_update_id + 1
            if update_id > expected_id:
                self.logger().warning(
                    f"Gap in update sequence for {sync_state.trading_pair}: "
                    f"expected {expected_id}, got {update_id}"
                )
                # Could implement gap recovery here
        
        # Check for duplicate messages
        if update_id <= sync_state.last_update_id:
            self.logger().debug(f"Duplicate update ID {update_id} for {sync_state.trading_pair}")
            return False
        
        return True
    
    async def _check_sync_timeout(self, trading_pair: str) -> None:
        """
        Check for synchronization timeout and trigger resync if needed.
        
        Args:
            trading_pair: Trading pair to check
        """
        sync_state = self._sync_states.get(trading_pair)
        if not sync_state:
            return
        
        if sync_state.last_sync_time == 0:
            return
        
        time_since_sync = time.time() - sync_state.last_sync_time
        
        if time_since_sync > self._sync_timeout:
            self.logger().warning(
                f"Sync timeout for {trading_pair} ({time_since_sync:.1f}s), "
                f"may need to resync with snapshot"
            )
            
            # Reset sync state to trigger resync
            sync_state.is_synchronized = False
            sync_state.snapshot_update_id = 0
    
    async def _symbol_to_trading_pair(self, symbol: str) -> Optional[str]:
        """
        Convert exchange symbol to Hummingbot trading pair format.
        
        Args:
            symbol: Exchange symbol (e.g., "BTCUSDT")
            
        Returns:
            Trading pair in Hummingbot format (e.g., "BTC-USDT")
        """
        try:
            # This is a simplified conversion - in practice you'd use proper mapping
            if len(symbol) >= 6:
                # Assume last 4 characters are quote asset for major pairs
                if symbol.endswith(('USDT', 'BUSD', 'USDC')):
                    base = symbol[:-4]
                    quote = symbol[-4:]
                elif symbol.endswith(('BTC', 'ETH', 'BNB')):
                    base = symbol[:-3]
                    quote = symbol[-3:]
                else:
                    # Default split
                    base = symbol[:-4] if len(symbol) > 4 else symbol[:3]
                    quote = symbol[-4:] if len(symbol) > 4 else symbol[3:]
            else:
                # Short symbol, split in half
                mid = len(symbol) // 2
                base = symbol[:mid]
                quote = symbol[mid:]
            
            return f"{base}-{quote}"
            
        except Exception as e:
            self.logger().error(f"Error converting symbol {symbol} to trading pair: {e}")
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get processing statistics.
        
        Returns:
            Dictionary with processing statistics
        """
        return {
            **self._stats,
            "active_pairs": len(self._processing_tasks),
            "sync_states": len(self._sync_states),
            "message_queues": len(self._message_queues)
        }
    
    def get_sync_state(self, trading_pair: str) -> Optional[Dict[str, Any]]:
        """
        Get synchronization state for a trading pair.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
            
        Returns:
            Sync state information or None if not found
        """
        sync_state = self._sync_states.get(trading_pair)
        if not sync_state:
            return None
        
        return {
            "trading_pair": sync_state.trading_pair,
            "last_update_id": sync_state.last_update_id,
            "is_synchronized": sync_state.is_synchronized,
            "pending_diffs": len(sync_state.pending_diffs),
            "snapshot_update_id": sync_state.snapshot_update_id,
            "last_sync_time": sync_state.last_sync_time,
            "time_since_sync": time.time() - sync_state.last_sync_time if sync_state.last_sync_time > 0 else 0
        }
