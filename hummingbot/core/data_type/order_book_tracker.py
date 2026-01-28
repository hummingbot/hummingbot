import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Dict, List, Optional, Tuple

import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.event.events import OrderBookTradeEvent
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class OrderBookTrackerDataSourceType(Enum):
    REMOTE_API = 2
    EXCHANGE_API = 3


@dataclass
class LatencyStats:
    """
    Tracks latency statistics with rolling window for recent samples.
    All times are in milliseconds.

    Supports sampling to reduce overhead on high-frequency message streams.
    """
    ROLLING_WINDOW_SIZE: int = 100  # Keep last 100 samples for recent average
    SAMPLE_RATE: int = 10  # Record 1 out of every N messages for latency (set to 1 to record all)

    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float('inf')
    max_ms: float = 0.0
    _recent_samples: Deque = field(default_factory=lambda: deque(maxlen=100))
    _sample_counter: int = 0  # Internal counter for sampling

    def record(self, latency_ms: float):
        """
        Record a new latency sample.

        Uses sampling to reduce overhead - only records latency details
        for every SAMPLE_RATE messages, but always updates count.
        """
        self.count += 1
        self._sample_counter += 1

        # Always track min/max (cheap operations)
        if latency_ms < self.min_ms:
            self.min_ms = latency_ms
        if latency_ms > self.max_ms:
            self.max_ms = latency_ms

        # Only record full stats every SAMPLE_RATE messages to reduce overhead
        if self._sample_counter >= self.SAMPLE_RATE:
            self._sample_counter = 0
            self.total_ms += latency_ms * self.SAMPLE_RATE  # Approximate total
            self._recent_samples.append(latency_ms)

    @property
    def avg_ms(self) -> float:
        """All-time average latency."""
        return self.total_ms / self.count if self.count > 0 else 0.0

    @property
    def recent_avg_ms(self) -> float:
        """Average latency over recent samples."""
        return sum(self._recent_samples) / len(self._recent_samples) if self._recent_samples else 0.0

    @property
    def recent_samples_count(self) -> int:
        """Number of samples in the rolling window."""
        return len(self._recent_samples)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "count": self.count,
            "total_ms": self.total_ms,
            "min_ms": self.min_ms if self.min_ms != float('inf') else 0.0,
            "max_ms": self.max_ms,
            "avg_ms": self.avg_ms,
            "recent_avg_ms": self.recent_avg_ms,
            "recent_samples_count": self.recent_samples_count,
        }


@dataclass
class OrderBookPairMetrics:
    """Metrics for a single trading pair."""
    trading_pair: str

    # Message counts
    diffs_processed: int = 0
    diffs_rejected: int = 0
    snapshots_processed: int = 0
    trades_processed: int = 0
    trades_rejected: int = 0

    # Timestamps (perf_counter for internal timing)
    last_diff_timestamp: float = 0.0
    last_snapshot_timestamp: float = 0.0
    last_trade_timestamp: float = 0.0
    tracking_start_time: float = 0.0

    # Latency tracking
    diff_processing_latency: LatencyStats = field(default_factory=LatencyStats)
    snapshot_processing_latency: LatencyStats = field(default_factory=LatencyStats)
    trade_processing_latency: LatencyStats = field(default_factory=LatencyStats)

    def messages_per_minute(self, current_time: float) -> Dict[str, float]:
        """Calculate messages per minute rates."""
        elapsed_minutes = (current_time - self.tracking_start_time) / 60.0 if self.tracking_start_time > 0 else 0
        if elapsed_minutes <= 0:
            return {"diffs": 0.0, "snapshots": 0.0, "trades": 0.0, "total": 0.0}

        diffs_per_min = self.diffs_processed / elapsed_minutes
        snapshots_per_min = self.snapshots_processed / elapsed_minutes
        trades_per_min = self.trades_processed / elapsed_minutes

        return {
            "diffs": diffs_per_min,
            "snapshots": snapshots_per_min,
            "trades": trades_per_min,
            "total": diffs_per_min + snapshots_per_min + trades_per_min,
        }

    def to_dict(self, current_time: float) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "trading_pair": self.trading_pair,
            "diffs_processed": self.diffs_processed,
            "diffs_rejected": self.diffs_rejected,
            "snapshots_processed": self.snapshots_processed,
            "trades_processed": self.trades_processed,
            "trades_rejected": self.trades_rejected,
            "last_diff_timestamp": self.last_diff_timestamp,
            "last_snapshot_timestamp": self.last_snapshot_timestamp,
            "last_trade_timestamp": self.last_trade_timestamp,
            "tracking_start_time": self.tracking_start_time,
            "messages_per_minute": self.messages_per_minute(current_time),
            "diff_latency": self.diff_processing_latency.to_dict(),
            "snapshot_latency": self.snapshot_processing_latency.to_dict(),
            "trade_latency": self.trade_processing_latency.to_dict(),
        }


@dataclass
class OrderBookTrackerMetrics:
    """Aggregate metrics for the entire order book tracker."""

    # Global message counts
    total_diffs_processed: int = 0
    total_diffs_rejected: int = 0
    total_diffs_queued: int = 0  # Messages queued before tracking ready
    total_snapshots_processed: int = 0
    total_snapshots_rejected: int = 0
    total_trades_processed: int = 0
    total_trades_rejected: int = 0

    # Timing
    tracker_start_time: float = 0.0

    # Global latency stats
    diff_processing_latency: LatencyStats = field(default_factory=LatencyStats)
    snapshot_processing_latency: LatencyStats = field(default_factory=LatencyStats)
    trade_processing_latency: LatencyStats = field(default_factory=LatencyStats)

    # Per-pair metrics
    per_pair_metrics: Dict[str, OrderBookPairMetrics] = field(default_factory=dict)

    def get_or_create_pair_metrics(self, trading_pair: str) -> OrderBookPairMetrics:
        """Get or create metrics for a trading pair."""
        if trading_pair not in self.per_pair_metrics:
            self.per_pair_metrics[trading_pair] = OrderBookPairMetrics(
                trading_pair=trading_pair,
                tracking_start_time=time.perf_counter(),
            )
        return self.per_pair_metrics[trading_pair]

    def remove_pair_metrics(self, trading_pair: str):
        """Remove metrics for a trading pair."""
        self.per_pair_metrics.pop(trading_pair, None)

    def messages_per_minute(self, current_time: float) -> Dict[str, float]:
        """Calculate global messages per minute rates."""
        elapsed_minutes = (current_time - self.tracker_start_time) / 60.0 if self.tracker_start_time > 0 else 0
        if elapsed_minutes <= 0:
            return {"diffs": 0.0, "snapshots": 0.0, "trades": 0.0, "total": 0.0}

        diffs_per_min = self.total_diffs_processed / elapsed_minutes
        snapshots_per_min = self.total_snapshots_processed / elapsed_minutes
        trades_per_min = self.total_trades_processed / elapsed_minutes

        return {
            "diffs": diffs_per_min,
            "snapshots": snapshots_per_min,
            "trades": trades_per_min,
            "total": diffs_per_min + snapshots_per_min + trades_per_min,
        }

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        current_time = time.perf_counter()
        return {
            "total_diffs_processed": self.total_diffs_processed,
            "total_diffs_rejected": self.total_diffs_rejected,
            "total_diffs_queued": self.total_diffs_queued,
            "total_snapshots_processed": self.total_snapshots_processed,
            "total_snapshots_rejected": self.total_snapshots_rejected,
            "total_trades_processed": self.total_trades_processed,
            "total_trades_rejected": self.total_trades_rejected,
            "tracker_start_time": self.tracker_start_time,
            "uptime_seconds": current_time - self.tracker_start_time if self.tracker_start_time > 0 else 0,
            "messages_per_minute": self.messages_per_minute(current_time),
            "diff_latency": self.diff_processing_latency.to_dict(),
            "snapshot_latency": self.snapshot_processing_latency.to_dict(),
            "trade_latency": self.trade_processing_latency.to_dict(),
            "per_pair_metrics": {
                pair: metrics.to_dict(current_time)
                for pair, metrics in self.per_pair_metrics.items()
            },
        }


class OrderBookTracker:
    PAST_DIFF_WINDOW_SIZE: int = 32
    _obt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._obt_logger is None:
            cls._obt_logger = logging.getLogger(__name__)
        return cls._obt_logger

    def __init__(self, data_source: OrderBookTrackerDataSource, trading_pairs: List[str], domain: Optional[str] = None):
        self._domain: Optional[str] = domain
        self._data_source: OrderBookTrackerDataSource = data_source
        self._trading_pairs: List[str] = trading_pairs
        self._order_books_initialized: asyncio.Event = asyncio.Event()
        self._tracking_tasks: Dict[str, asyncio.Task] = {}
        self._order_books: Dict[str, OrderBook] = {}
        self._tracking_message_queues: Dict[str, asyncio.Queue] = {}
        self._past_diffs_windows: Dict[str, Deque] = defaultdict(lambda: deque(maxlen=self.PAST_DIFF_WINDOW_SIZE))
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_trade_stream: asyncio.Queue = asyncio.Queue()
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._saved_message_queues: Dict[str, Deque[OrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))

        self._emit_trade_event_task: Optional[asyncio.Task] = None
        self._init_order_books_task: Optional[asyncio.Task] = None
        self._order_book_diff_listener_task: Optional[asyncio.Task] = None
        self._order_book_trade_listener_task: Optional[asyncio.Task] = None
        self._order_book_snapshot_listener_task: Optional[asyncio.Task] = None
        self._order_book_diff_router_task: Optional[asyncio.Task] = None
        self._order_book_snapshot_router_task: Optional[asyncio.Task] = None
        self._update_last_trade_prices_task: Optional[asyncio.Task] = None
        self._order_book_stream_listener_task: Optional[asyncio.Task] = None

        # Metrics tracking
        self._metrics: OrderBookTrackerMetrics = OrderBookTrackerMetrics()

    @property
    def metrics(self) -> OrderBookTrackerMetrics:
        """Access order book tracker metrics."""
        return self._metrics

    @property
    def data_source(self) -> OrderBookTrackerDataSource:
        return self._data_source

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_books

    @property
    def ready(self) -> bool:
        return self._order_books_initialized.is_set()

    @property
    def snapshot(self) -> Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]:
        return {
            trading_pair: order_book.snapshot
            for trading_pair, order_book in self._order_books.items()
        }

    def start(self):
        self.stop()
        self._metrics.tracker_start_time = time.perf_counter()
        self._init_order_books_task = safe_ensure_future(
            self._init_order_books()
        )
        self._emit_trade_event_task = safe_ensure_future(
            self._emit_trade_event_loop()
        )
        self._order_book_diff_listener_task = safe_ensure_future(
            self._data_source.listen_for_order_book_diffs(self._ev_loop, self._order_book_diff_stream)
        )
        self._order_book_trade_listener_task = safe_ensure_future(
            self._data_source.listen_for_trades(self._ev_loop, self._order_book_trade_stream)
        )
        self._order_book_snapshot_listener_task = safe_ensure_future(
            self._data_source.listen_for_order_book_snapshots(self._ev_loop, self._order_book_snapshot_stream)
        )
        self._order_book_stream_listener_task = safe_ensure_future(
            self._data_source.listen_for_subscriptions()
        )
        self._order_book_diff_router_task = safe_ensure_future(
            self._order_book_diff_router()
        )
        self._order_book_snapshot_router_task = safe_ensure_future(
            self._order_book_snapshot_router()
        )
        self._update_last_trade_prices_task = safe_ensure_future(
            self._update_last_trade_prices_loop()
        )

    def stop(self):
        if self._init_order_books_task is not None:
            self._init_order_books_task.cancel()
            self._init_order_books_task = None
        if self._emit_trade_event_task is not None:
            self._emit_trade_event_task.cancel()
            self._emit_trade_event_task = None
        if self._order_book_diff_listener_task is not None:
            self._order_book_diff_listener_task.cancel()
            self._order_book_diff_listener_task = None
        if self._order_book_snapshot_listener_task is not None:
            self._order_book_snapshot_listener_task.cancel()
            self._order_book_snapshot_listener_task = None
        if self._order_book_trade_listener_task is not None:
            self._order_book_trade_listener_task.cancel()
            self._order_book_trade_listener_task = None

        if self._order_book_diff_router_task is not None:
            self._order_book_diff_router_task.cancel()
            self._order_book_diff_router_task = None
        if self._order_book_snapshot_router_task is not None:
            self._order_book_snapshot_router_task.cancel()
            self._order_book_snapshot_router_task = None
        if self._update_last_trade_prices_task is not None:
            self._update_last_trade_prices_task.cancel()
            self._update_last_trade_prices_task = None
        if self._order_book_stream_listener_task is not None:
            self._order_book_stream_listener_task.cancel()
        if len(self._tracking_tasks) > 0:
            for _, task in self._tracking_tasks.items():
                task.cancel()
            self._tracking_tasks.clear()
        self._order_books_initialized.clear()

    async def wait_ready(self):
        await self._order_books_initialized.wait()

    async def _update_last_trade_prices_loop(self):
        '''
        Updates last trade price for all order books through REST API, it is to initiate last_trade_price and as
        fall-back mechanism for when the web socket update channel fails.
        '''
        await self._order_books_initialized.wait()
        while True:
            try:
                outdateds = [t_pair for t_pair, o_book in self._order_books.items()
                             if o_book.last_applied_trade < time.perf_counter() - (60. * 3)
                             and o_book.last_trade_price_rest_updated < time.perf_counter() - 5]
                if outdateds:
                    args = {"trading_pairs": outdateds}
                    if self._domain is not None:
                        args["domain"] = self._domain
                    last_prices = await self._data_source.get_last_traded_prices(**args)
                    for trading_pair, last_price in last_prices.items():
                        self._order_books[trading_pair].last_trade_price = last_price
                        self._order_books[trading_pair].last_trade_price_rest_updated = time.perf_counter()
                else:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching last trade price.", exc_info=True)
                await asyncio.sleep(30)

    async def _initial_order_book_for_trading_pair(self, trading_pair: str) -> OrderBook:
        return await self._data_source.get_new_order_book(trading_pair)

    async def _init_order_books(self):
        """
        Initialize order books
        """
        for index, trading_pair in enumerate(self._trading_pairs):
            self._order_books[trading_pair] = await self._initial_order_book_for_trading_pair(trading_pair)
            self._tracking_message_queues[trading_pair] = asyncio.Queue()
            self._tracking_tasks[trading_pair] = safe_ensure_future(self._track_single_book(trading_pair))
            self.logger().info(f"Initialized order book for {trading_pair}. "
                               f"{index + 1}/{len(self._trading_pairs)} completed.")
            await self._sleep(delay=1)
        self._order_books_initialized.set()

    async def add_trading_pair(self, trading_pair: str) -> bool:
        """
        Dynamically adds a new trading pair to the order book tracker.

        This method:
        1. Subscribes to the trading pair on the existing WebSocket connection
        2. Fetches the initial order book snapshot
        3. Creates the tracking queue and starts the tracking task
        4. Any messages received before the snapshot (stored in _saved_message_queues)
           will be automatically processed by _track_single_book

        :param trading_pair: the trading pair to add (e.g., "BTC-USDT")
        :return: True if successfully added, False otherwise
        """
        # Check if already tracking this pair
        if trading_pair in self._order_books:
            self.logger().warning(f"Trading pair {trading_pair} is already being tracked")
            return False

        # Wait for initial order books to be ready before adding new ones
        await self._order_books_initialized.wait()

        try:
            self.logger().info(f"Adding trading pair {trading_pair} to order book tracker...")

            # Step 1: Subscribe to WebSocket channels for this pair
            # This ensures we start receiving diff messages immediately
            subscribe_success = await self._data_source.subscribe_to_trading_pair(trading_pair)
            if not subscribe_success:
                self.logger().error(f"Failed to subscribe to {trading_pair} WebSocket channels")
                return False

            # Step 2: Add to internal trading pairs list
            if trading_pair not in self._trading_pairs:
                self._trading_pairs.append(trading_pair)

            # Step 3: Fetch initial snapshot and create order book
            # Note: Diffs received during this time are saved in _saved_message_queues
            self._order_books[trading_pair] = await self._initial_order_book_for_trading_pair(trading_pair)

            # Step 4: Create message queue and start tracking task
            self._tracking_message_queues[trading_pair] = asyncio.Queue()
            self._tracking_tasks[trading_pair] = safe_ensure_future(
                self._track_single_book(trading_pair)
            )

            self.logger().info(f"Successfully added trading pair {trading_pair} to order book tracker")
            return True

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error adding trading pair {trading_pair}")
            # Clean up partial state
            self._order_books.pop(trading_pair, None)
            self._tracking_message_queues.pop(trading_pair, None)
            if trading_pair in self._tracking_tasks:
                self._tracking_tasks[trading_pair].cancel()
                self._tracking_tasks.pop(trading_pair, None)
            return False

    async def remove_trading_pair(self, trading_pair: str) -> bool:
        """
        Dynamically removes a trading pair from the order book tracker.

        This method:
        1. Cancels the tracking task for the pair
        2. Unsubscribes from WebSocket channels
        3. Cleans up all data structures

        :param trading_pair: the trading pair to remove (e.g., "SOL-USDT")
        :return: True if successfully removed, False otherwise
        """
        # Check if we're tracking this pair
        if trading_pair not in self._order_books:
            self.logger().warning(f"Trading pair {trading_pair} is not being tracked")
            return False

        try:
            self.logger().info(f"Removing trading pair {trading_pair} from order book tracker...")

            # Step 1: Cancel the tracking task
            if trading_pair in self._tracking_tasks:
                self._tracking_tasks[trading_pair].cancel()
                try:
                    await self._tracking_tasks[trading_pair]
                except asyncio.CancelledError:
                    pass
                self._tracking_tasks.pop(trading_pair, None)

            # Step 2: Unsubscribe from WebSocket channels
            unsubscribe_success = await self._data_source.unsubscribe_from_trading_pair(trading_pair)
            if not unsubscribe_success:
                self.logger().warning(f"Failed to unsubscribe from {trading_pair} WebSocket channels")
                # Continue with cleanup anyway

            # Step 3: Clean up data structures
            self._order_books.pop(trading_pair, None)
            self._tracking_message_queues.pop(trading_pair, None)
            self._past_diffs_windows.pop(trading_pair, None)
            self._saved_message_queues.pop(trading_pair, None)

            # Step 4: Clean up metrics for this pair
            self._metrics.remove_pair_metrics(trading_pair)

            # Step 5: Remove from trading pairs list
            if trading_pair in self._trading_pairs:
                self._trading_pairs.remove(trading_pair)

            self.logger().info(f"Successfully removed trading pair {trading_pair} from order book tracker")
            return True

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error removing trading pair {trading_pair}")
            return False

    async def _order_book_diff_router(self):
        """
        Routes the real-time order book diff messages to the correct order book.
        """
        last_message_timestamp: float = time.time()
        messages_queued: int = 0
        messages_accepted: int = 0
        messages_rejected: int = 0

        # Cache pair_metrics references to avoid repeated dict lookups
        pair_metrics_cache: Dict[str, OrderBookPairMetrics] = {}

        while True:
            try:
                ob_message: OrderBookMessage = await self._order_book_diff_stream.get()
                process_start = time.perf_counter()
                trading_pair: str = ob_message.trading_pair

                if trading_pair not in self._tracking_message_queues:
                    messages_queued += 1
                    self._metrics.total_diffs_queued += 1
                    # Save diff messages received before snapshots are ready
                    self._saved_message_queues[trading_pair].append(ob_message)
                    continue

                message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
                order_book: OrderBook = self._order_books[trading_pair]

                # Get or cache pair metrics (single lookup per pair)
                if trading_pair not in pair_metrics_cache:
                    pair_metrics_cache[trading_pair] = self._metrics.get_or_create_pair_metrics(trading_pair)
                pair_metrics = pair_metrics_cache[trading_pair]

                # Check the order book's initial update ID. If it's larger, don't bother.
                if order_book.snapshot_uid > ob_message.update_id:
                    messages_rejected += 1
                    self._metrics.total_diffs_rejected += 1
                    pair_metrics.diffs_rejected += 1
                    continue

                await message_queue.put(ob_message)
                messages_accepted += 1

                # Record metrics (latency uses sampling internally to reduce overhead)
                process_time_ms = (time.perf_counter() - process_start) * 1000
                self._metrics.total_diffs_processed += 1
                self._metrics.diff_processing_latency.record(process_time_ms)
                pair_metrics.diffs_processed += 1
                pair_metrics.last_diff_timestamp = process_start
                pair_metrics.diff_processing_latency.record(process_time_ms)

                # Log some statistics.
                now: float = time.time()
                if int(now / 60.0) > int(last_message_timestamp / 60.0):
                    self.logger().debug(f"Diff messages processed: {messages_accepted}, "
                                        f"rejected: {messages_rejected}, queued: {messages_queued}")
                    messages_accepted = 0
                    messages_rejected = 0
                    messages_queued = 0

                last_message_timestamp = now
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error routing order book messages.",
                    exc_info=True,
                    app_warning_msg="Unexpected error routing order book messages. Retrying after 5 seconds."
                )
                await asyncio.sleep(5.0)

    async def _order_book_snapshot_router(self):
        """
        Route the real-time order book snapshot messages to the correct order book.
        """
        await self._order_books_initialized.wait()

        # Cache pair_metrics references
        pair_metrics_cache: Dict[str, OrderBookPairMetrics] = {}

        while True:
            try:
                ob_message: OrderBookMessage = await self._order_book_snapshot_stream.get()
                process_start = time.perf_counter()
                trading_pair: str = ob_message.trading_pair

                if trading_pair not in self._tracking_message_queues:
                    self._metrics.total_snapshots_rejected += 1
                    continue

                message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
                await message_queue.put(ob_message)

                # Record metrics
                process_time_ms = (time.perf_counter() - process_start) * 1000
                self._metrics.total_snapshots_processed += 1
                self._metrics.snapshot_processing_latency.record(process_time_ms)

                # Get or cache pair metrics
                if trading_pair not in pair_metrics_cache:
                    pair_metrics_cache[trading_pair] = self._metrics.get_or_create_pair_metrics(trading_pair)
                pair_metrics = pair_metrics_cache[trading_pair]
                pair_metrics.snapshots_processed += 1
                pair_metrics.last_snapshot_timestamp = process_start
                pair_metrics.snapshot_processing_latency.record(process_time_ms)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 5 seconds.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _track_single_book(self, trading_pair: str):
        past_diffs_window = self._past_diffs_windows[trading_pair]

        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: OrderBook = self._order_books[trading_pair]
        last_message_timestamp: float = time.time()
        diff_messages_accepted: int = 0

        while True:
            try:
                saved_messages: Deque[OrderBookMessage] = self._saved_message_queues[trading_pair]

                # Process saved messages first if there are any
                if len(saved_messages) > 0:
                    message = saved_messages.popleft()
                else:
                    message = await message_queue.get()

                if message.type is OrderBookMessageType.DIFF:
                    order_book.apply_diffs(message.bids, message.asks, message.update_id)
                    past_diffs_window.append(message)
                    diff_messages_accepted += 1

                    # Output some statistics periodically.
                    now: float = time.time()
                    if int(now / 60.0) > int(last_message_timestamp / 60.0):
                        self.logger().debug(f"Processed {diff_messages_accepted} order book diffs for {trading_pair}.")
                        diff_messages_accepted = 0
                    last_message_timestamp = now
                elif message.type is OrderBookMessageType.SNAPSHOT:
                    past_diffs: List[OrderBookMessage] = list(past_diffs_window)
                    order_book.restore_from_snapshot_and_diffs(message, past_diffs)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error tracking order book for {trading_pair}.",
                    exc_info=True,
                    app_warning_msg="Unexpected error tracking order book. Retrying after 5 seconds."
                )
                await asyncio.sleep(5.0)

    async def _emit_trade_event_loop(self):
        last_message_timestamp: float = time.time()
        messages_accepted: int = 0
        messages_rejected: int = 0
        await self._order_books_initialized.wait()

        # Cache pair_metrics references
        pair_metrics_cache: Dict[str, OrderBookPairMetrics] = {}

        while True:
            try:
                trade_message: OrderBookMessage = await self._order_book_trade_stream.get()
                process_start = time.perf_counter()
                trading_pair: str = trade_message.trading_pair

                if trading_pair not in self._order_books:
                    messages_rejected += 1
                    self._metrics.total_trades_rejected += 1
                    continue

                order_book: OrderBook = self._order_books[trading_pair]
                order_book.apply_trade(OrderBookTradeEvent(
                    trading_pair=trade_message.trading_pair,
                    timestamp=trade_message.timestamp,
                    price=float(trade_message.content["price"]),
                    amount=float(trade_message.content["amount"]),
                    trade_id=trade_message.trade_id,
                    type=TradeType.SELL if
                    trade_message.content["trade_type"] == float(TradeType.SELL.value) else TradeType.BUY
                ))

                messages_accepted += 1

                # Record metrics
                process_time_ms = (time.perf_counter() - process_start) * 1000
                self._metrics.total_trades_processed += 1
                self._metrics.trade_processing_latency.record(process_time_ms)

                # Get or cache pair metrics
                if trading_pair not in pair_metrics_cache:
                    pair_metrics_cache[trading_pair] = self._metrics.get_or_create_pair_metrics(trading_pair)
                pair_metrics = pair_metrics_cache[trading_pair]
                pair_metrics.trades_processed += 1
                pair_metrics.last_trade_timestamp = process_start
                pair_metrics.trade_processing_latency.record(process_time_ms)

                # Log some statistics.
                now: float = time.time()
                if int(now / 60.0) > int(last_message_timestamp / 60.0):
                    self.logger().debug(f"Trade messages processed: {messages_accepted}, rejected: {messages_rejected}")
                    messages_accepted = 0
                    messages_rejected = 0

                last_message_timestamp = now
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error routing order book messages.",
                    exc_info=True,
                    app_warning_msg="Unexpected error routing order book messages. Retrying after 5 seconds."
                )
                await asyncio.sleep(5.0)

    @staticmethod
    async def _sleep(delay: float):
        await asyncio.sleep(delay=delay)
