import asyncio
import logging
from typing import Dict, List, Optional

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.logger import HummingbotLogger

from .evedex_perpetual_api_order_book_data_source import EvedexPerpetualAPIOrderBookDataSource

logger = logging.getLogger(__name__)


class EvedexPerpetualOrderBookTracker(OrderBookTracker):
    """
    Order book tracker for EVEDEX Perpetual.
    Manages order book synchronization and updates.
    """
    
    _logger: Optional[HummingbotLogger] = None
    
    @classmethod
    def logger(cls) -> HummingbotLogger:
        """Get logger instance."""
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger
    
    def __init__(
        self,
        data_source: EvedexPerpetualAPIOrderBookDataSource,
        trading_pairs: List[str],
    ):
        """
        Initialize order book tracker.
        
        Args:
            data_source: Data source for order book updates
            trading_pairs: List of trading pairs to track
        """
        super().__init__(
            data_source=data_source,
            trading_pairs=trading_pairs,
        )
        
        self._order_books: Dict[str, OrderBook] = {}
        self._tracking_tasks: Dict[str, asyncio.Task] = {}
        
    @property
    def exchange_name(self) -> str:
        """Exchange name."""
        return "evedex_perpetual"
    
    async def start(self):
        """Start order book tracking."""
        await super().start()
        
        # Start tracking tasks for each trading pair
        for trading_pair in self._trading_pairs:
            if trading_pair not in self._tracking_tasks:
                task = asyncio.create_task(
                    self._track_single_book(trading_pair)
                )
                self._tracking_tasks[trading_pair] = task
    
    async def stop(self):
        """Stop order book tracking."""
        # Cancel all tracking tasks
        for task in self._tracking_tasks.values():
            task.cancel()
        
        self._tracking_tasks.clear()
        await super().stop()
    
    async def _track_single_book(self, trading_pair: str):
        """
        Track a single order book.
        
        Args:
            trading_pair: Trading pair to track
        """
        while True:
            try:
                # Get initial snapshot
                snapshot_data = await self._data_source.get_order_book_snapshot(
                    trading_pair
                )
                
                # Create or update order book
                if trading_pair not in self._order_books:
                    self._order_books[trading_pair] = OrderBook()
                
                order_book = self._order_books[trading_pair]
                
                # Apply snapshot
                order_book.apply_snapshot(
                    snapshot_data["bids"],
                    snapshot_data["asks"],
                    snapshot_data["update_id"],
                )
                
                self.logger().info(
                    f"Initialized order book for {trading_pair} "
                    f"(update_id: {snapshot_data['update_id']})"
                )
                
                # Listen for updates
                await self._listen_for_order_book_diffs(trading_pair)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Error tracking order book for {trading_pair}: {e}",
                    exc_info=True
                )
                await asyncio.sleep(5)
    
    async def _listen_for_order_book_diffs(self, trading_pair: str):
        """
        Listen for order book diff updates.
        
        Args:
            trading_pair: Trading pair to listen for
        """
        message_queue = asyncio.Queue()
        
        # Start listening task
        listen_task = asyncio.create_task(
            self._data_source.listen_for_order_book_diffs(message_queue)
        )
        
        try:
            while True:
                try:
                    message: OrderBookMessage = await asyncio.wait_for(
                        message_queue.get(), timeout=60.0
                    )
                    
                    # Filter for this trading pair
                    if message.content.get("trading_pair") != trading_pair:
                        continue
                    
                    # Apply diff update
                    order_book = self._order_books.get(trading_pair)
                    if order_book:
                        if message.type == OrderBookMessageType.DIFF:
                            order_book.apply_diffs(
                                message.content["bids"],
                                message.content["asks"],
                                message.content["update_id"],
                            )
                        elif message.type == OrderBookMessageType.SNAPSHOT:
                            order_book.apply_snapshot(
                                message.content["bids"],
                                message.content["asks"],
                                message.content["update_id"],
                            )
                    
                except asyncio.TimeoutError:
                    # Refresh snapshot periodically
                    self.logger().debug(
                        f"No updates for {trading_pair} for 60s, refreshing snapshot"
                    )
                    break
                    
        except asyncio.CancelledError:
            raise
        finally:
            listen_task.cancel()
    
    def get_order_book(self, trading_pair: str) -> Optional[OrderBook]:
        """
        Get order book for trading pair.
        
        Args:
            trading_pair: Trading pair
            
        Returns:
            OrderBook instance or None
        """
        return self._order_books.get(trading_pair)
