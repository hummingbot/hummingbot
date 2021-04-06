import asyncio
import logging
# import sys
from collections import deque, defaultdict
from typing import (
    Optional,
    Deque,
    List,
    Dict,
    # Set
)
from hummingbot.connector.exchange.dydx.dydx_active_order_tracker import DydxActiveOrderTracker
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.connector.exchange.dydx.dydx_order_book import DydxOrderBook
from hummingbot.connector.exchange.dydx.dydx_order_book_message import DydxOrderBookMessage
from hummingbot.connector.exchange.dydx.dydx_api_order_book_data_source import DydxAPIOrderBookDataSource
from hummingbot.connector.exchange.dydx.dydx_auth import DydxAuth
from hummingbot.connector.exchange.dydx.dydx_api_token_configuration_data_source import DydxAPITokenConfigurationDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class DydxOrderBookTracker(OrderBookTracker):
    _dobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._dobt_logger is None:
            cls._dobt_logger = logging.getLogger(__name__)
        return cls._dobt_logger

    def __init__(
        self,
        trading_pairs: Optional[List[str]] = None,
        rest_api_url: str = "https://api.dydx.exchange/v1",
        websocket_url: str = "wss://api.dydx.exchange/v1/ws",
        dydx_auth: str = "",
        token_configuration: DydxAPITokenConfigurationDataSource = None,
    ):
        super().__init__(
            DydxAPIOrderBookDataSource(
                trading_pairs=trading_pairs,
                rest_api_url=rest_api_url,
                websocket_url=websocket_url,
                token_configuration=token_configuration
            ),
            trading_pairs)

        self._order_books: Dict[str, DydxOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[DydxOrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_trade_stream: asyncio.Queue = asyncio.Queue()
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._dydx_auth = DydxAuth(dydx_auth)
        self._token_configuration: DydxAPITokenConfigurationDataSource = token_configuration
        self._active_order_trackers: Dict[str, DydxActiveOrderTracker] = defaultdict(lambda: DydxActiveOrderTracker(self.token_configuration))

    @property
    def token_configuration(self) -> DydxAPITokenConfigurationDataSource:
        if not self._token_configuration:
            self._token_configuration = DydxAPITokenConfigurationDataSource.create()
        return self._token_configuration

    @property
    def exchange_name(self) -> str:
        return "dydx"

    async def _track_single_book(self, trading_pair: str):
        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: DydxOrderBook = self._order_books[trading_pair]
        active_order_tracker: DydxActiveOrderTracker = self._active_order_trackers[trading_pair]
        while True:
            try:
                message: DydxOrderBookMessage = None
                saved_messages: Deque[DydxOrderBookMessage] = self._saved_message_queues[trading_pair]
                # Process saved messages first if there are any
                if len(saved_messages) > 0:
                    message = saved_messages.popleft()
                else:
                    message = await message_queue.get()
                if message.type is OrderBookMessageType.DIFF:
                    bids, asks = active_order_tracker.convert_diff_message_to_order_book_row(message)
                    order_book.apply_diffs(bids, asks, int(message.timestamp))

                elif message.type is OrderBookMessageType.SNAPSHOT:
                    s_bids, s_asks = active_order_tracker.convert_snapshot_message_to_order_book_row(message)
                    order_book.apply_snapshot(s_bids, s_asks, int(message.timestamp))
                    self.logger().debug(f"Processed order book snapshot for {trading_pair}.")

            except asyncio.CancelledError:
                raise
            except KeyError:
                pass
            except Exception:
                self.logger().network(
                    f"Unexpected error tracking order book for {trading_pair}.",
                    exc_info=True,
                    app_warning_msg="Unexpected error tracking order book. Retrying after 5 seconds.",
                )
                await asyncio.sleep(5.0)
