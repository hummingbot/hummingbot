# DISABLE SELECT PYLINT TESTS
# pylint: disable=bad-continuation, no-member, no-name-in-module, broad-except
# pylint: disable=too-many-instance-attributes
"""
 ╔════════════════════════════════════════════════════╗
 ║ ╔═╗╦═╗╔═╗╔═╗╦ ╦╔═╗╔╗╔╔═╗  ╔╦╗╔═╗╔╦╗╔═╗╔╗╔╔═╗╔╦╗╔═╗ ║
 ║ ║ ╦╠╦╝╠═╣╠═╝╠═╣║╣ ║║║║╣   ║║║║╣  ║ ╠═╣║║║║ ║ ║║║╣  ║
 ║ ╚═╝╩╚═╩ ╩╩  ╩ ╩╚═╝╝╚╝╚═╝  ╩ ╩╚═╝ ╩ ╩ ╩╝╚╝╚═╝═╩╝╚═╝ ║
 ║    DECENTRALIZED EXCHANGE HUMMINGBOT CONNECTOR     ║
 ╚════════════════════════════════════════════════════╝
~
forked from binance_order_book_tracker v1.0.0 fork
~
"""
# STANDARD MODULES
import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional

# HUMMINGBOT MODULES
from hummingbot.connector.exchange.graphene.graphene_api_order_book_data_source import GrapheneAPIOrderBookDataSource
from hummingbot.connector.exchange.graphene.graphene_constants import GrapheneConstants
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger

# GLOBAL CONSTANTS
CONSTANTS = GrapheneConstants()
DEV = False


class GrapheneOrderBookTracker(OrderBookTracker):
    """
    continually update the bids and asks for each trading pair
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        domain: str,
        trading_pairs: Optional[List[str]] = None,
        **__,
    ):
        # ~ print("GrapheneOrderBookTracker")
        self.domain = domain
        self.constants = GrapheneConstants(domain)

        super().__init__(
            data_source=GrapheneAPIOrderBookDataSource(
                trading_pairs=self.constants.chain.PAIRS,
                domain=domain,
            ),
            trading_pairs=self.constants.chain.PAIRS,
            domain=domain,
        )
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self.domain = domain
        self._saved_message_queues: Dict[str, Deque[OrderBookMessage]] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self._trading_pairs = self.constants.chain.PAIRS
        self._order_book_stream_listener_task: Optional[asyncio.Task] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        """
        a classmethod for logging
        """
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def dev_log(self, *args, **kwargs):
        """
        log only in dev mode
        """
        if DEV:
            self.logger().info(*args, **kwargs)

    @property
    def exchange_name(self) -> str:
        """
        the name of this graphene blockchain
        """
        return self.constants.chain.NAME

    def start(self):
        """
        Starts the background task that connects to the exchange
        and listens to order book updates and trade events.
        """
        super().start()
        self._order_book_stream_listener_task = safe_ensure_future(
            self._data_source.listen_for_subscriptions()
        )

    def stop(self):
        """
        Stops the background task
        """
        _ = (
            self._order_book_stream_listener_task
            and self._order_book_stream_listener_task.cancel()
        )
        super().stop()

    async def _order_book_diff_router(self):
        """
        Routes the real-time order book diff messages to the correct order book.
        """
        last_message_timestamp: float = time.time()
        messages_accepted: int = 0
        messages_rejected: int = 0
        messages_queued: int = 0
        while True:
            try:
                ob_message: OrderBookMessage = await self._order_book_diff_stream.get()
                trading_pair: str = ob_message.trading_pair

                if trading_pair not in self._tracking_message_queues:
                    messages_queued += 1
                    # Save diff messages received before snapshots are ready
                    self._saved_message_queues[trading_pair].append(ob_message)
                    continue
                message_queue: asyncio.Queue = self._tracking_message_queues[
                    trading_pair
                ]
                # Check the order book's initial update ID. If it's larger, don't bother
                order_book: OrderBook = self._order_books[trading_pair]

                if order_book.snapshot_uid > ob_message.update_id:
                    messages_rejected += 1
                    continue
                await message_queue.put(ob_message)
                messages_accepted += 1

                # Log some statistics.
                now: float = time.time()
                if int(now / 60.0) > int(last_message_timestamp / 60.0):
                    msg = (
                        f"Diff messages processed: {messages_accepted}, "
                        f"rejected: {messages_rejected}, queued: {messages_queued}"
                    )
                    self.logger().debug(msg)
                    messages_accepted = 0
                    messages_rejected = 0
                    messages_queued = 0
                last_message_timestamp = now
            except asyncio.CancelledError:
                msg = f"asyncio.CancelledError {__name__}"
                self.logger().exception(msg)
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error routing order book messages.",
                    exc_info=True,
                    app_warning_msg=(
                        "Error routing order book messages. Retrying in 5 seconds."
                    ),
                )
                await asyncio.sleep(5.0)

    async def _track_single_book(self, trading_pair: str):

        past_diffs_window: Deque[OrderBookMessage] = deque()
        self._past_diffs_windows[trading_pair] = past_diffs_window
        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: OrderBook = self._order_books[trading_pair]
        last_message_timestamp: float = time.time()
        diff_messages_accepted: int = 0

        while True:
            try:
                saved_messages: Deque[OrderBookMessage] = self._saved_message_queues[
                    trading_pair
                ]
                # Process saved messages first if there are any
                if len(saved_messages) > 0:
                    message = saved_messages.popleft()  # OrderBookMessage
                    diff_messages_accepted += len(saved_messages)
                else:
                    message = await message_queue.get()  # OrderBookMessage
                past_diffs: List[OrderBookMessage] = list(past_diffs_window)
                order_book.restore_from_snapshot_and_diffs(message, past_diffs)
                msg = f"Processed order book snapshot for {trading_pair}."
                self.logger().debug(msg)
                # Output some statistics periodically.
                now: float = time.time()
                if int(now / 60.0) > int(last_message_timestamp / 60.0):
                    self.logger().debug(
                        f"Processed {diff_messages_accepted} order book diffs for"
                        f" {trading_pair}."
                    )
                    diff_messages_accepted = 0
                last_message_timestamp = now
            except asyncio.CancelledError:
                msg = f"asyncio.CancelledError {__name__}"
                self.logger().exception(msg)
                raise
            except Exception:
                msg = f"Unexpected error tracking order book for {trading_pair}."
                self.logger().network(
                    msg,
                    exc_info=True,
                    app_warning_msg=(
                        "Unexpected error tracking order book. Retrying after 5"
                        " seconds."
                    ),
                )
                await asyncio.sleep(5.0)
