import asyncio
import bisect
import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional

from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.connector.exchange.gate_io.gate_io_active_order_tracker import GateIoActiveOrderTracker
from hummingbot.connector.exchange.gate_io.gate_io_api_order_book_data_source import GateIoAPIOrderBookDataSource
from hummingbot.connector.exchange.gate_io.gate_io_order_book import GateIoOrderBook
from hummingbot.connector.exchange.gate_io.gate_io_order_book_message import GateIoOrderBookMessage
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class GateIoOrderBookTracker(OrderBookTracker):
    PAST_DIFF_WINDOW_SIZE: int = 100
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
        self,
        throttler: Optional[AsyncThrottler] = None,
        trading_pairs: Optional[List[str]] = None,
        api_factory: Optional[WebAssistantsFactory] = None,
    ):
        super().__init__(GateIoAPIOrderBookDataSource(throttler, trading_pairs, api_factory), trading_pairs)

        self._ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_trade_stream: asyncio.Queue = asyncio.Queue()
        self._process_msg_deque_task: Optional[asyncio.Task] = None
        self._past_diffs_windows: Dict[str, Deque] = {}
        self._order_books: Dict[str, GateIoOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[GateIoOrderBookMessage]] = \
            defaultdict(lambda: deque(maxlen=1000))
        self._active_order_trackers: Dict[str, GateIoActiveOrderTracker] = defaultdict(GateIoActiveOrderTracker)
        self._order_book_stream_listener_task: Optional[asyncio.Task] = None
        self._order_book_trade_listener_task: Optional[asyncio.Task] = None
        self._order_book_stream_listener_task: Optional[asyncio.Task] = None

    @property
    def exchange_name(self) -> str:
        """
        Name of the current exchange
        """
        return CONSTANTS.EXCHANGE_NAME

    def start(self):
        super().start()
        self._order_book_stream_listener_task = safe_ensure_future(
            self._data_source.listen_for_subscriptions()
        )

    def stop(self):
        self._order_book_stream_listener_task and self._order_book_stream_listener_task.cancel()
        super().stop()

    async def _track_single_book(self, trading_pair: str):
        """
        Update an order book with changes from the latest batch of received messages
        """
        past_diffs_window: Deque[GateIoOrderBookMessage] = deque(maxlen=self.PAST_DIFF_WINDOW_SIZE)
        self._past_diffs_windows[trading_pair] = past_diffs_window

        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: GateIoOrderBook = self._order_books[trading_pair]
        active_order_tracker: GateIoActiveOrderTracker = self._active_order_trackers[trading_pair]

        last_message_timestamp: float = time.time()
        diff_messages_accepted: int = 0

        while True:
            try:
                message: GateIoOrderBookMessage = await message_queue.get()
                if message.type is OrderBookMessageType.DIFF:
                    bids, asks = active_order_tracker.convert_diff_message_to_order_book_row(message)
                    order_book.apply_diffs(bids, asks, message.update_id)
                    past_diffs_window.append(message)
                    diff_messages_accepted += 1

                    # Output some statistics periodically.
                    now: float = time.time()
                    if int(now / 60.0) > int(last_message_timestamp / 60.0):
                        self.logger().debug(f"Processed {diff_messages_accepted} order book diffs for {trading_pair}.")
                        diff_messages_accepted = 0
                    last_message_timestamp = now
                elif message.type is OrderBookMessageType.SNAPSHOT:
                    past_diffs: List[GateIoOrderBookMessage] = list(past_diffs_window)
                    # only replay diffs later than snapshot, first update active order with snapshot then replay diffs
                    replay_position = bisect.bisect_right(past_diffs, message)
                    replay_diffs = past_diffs[replay_position:]
                    s_bids, s_asks = active_order_tracker.convert_snapshot_message_to_order_book_row(message)
                    order_book.apply_snapshot(s_bids, s_asks, message.update_id)
                    for diff_message in replay_diffs:
                        d_bids, d_asks = active_order_tracker.convert_diff_message_to_order_book_row(diff_message)
                        order_book.apply_diffs(d_bids, d_asks, diff_message.update_id)

                    self.logger().debug(f"Processed order book snapshot for {trading_pair}.")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error processing order book messages for {trading_pair}.",
                    exc_info=True,
                    app_warning_msg="Unexpected error processing order book messages. Retrying after 5 seconds."
                )
                await asyncio.sleep(5.0)
