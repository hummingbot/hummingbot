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
from decimal import Decimal
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_order_book import DydxPerpetualOrderBook
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_order_book_message import DydxPerpetualOrderBookMessage
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_api_order_book_data_source import DydxPerpetualAPIOrderBookDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.order_book_row import ClientOrderBookRow


class DydxPerpetualOrderBookTracker(OrderBookTracker):
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
    ):
        super().__init__(
            DydxPerpetualAPIOrderBookDataSource(
                trading_pairs=trading_pairs,
                rest_api_url=rest_api_url,
                websocket_url=websocket_url,
            ),
            trading_pairs)

        self._order_books: Dict[str, DydxPerpetualOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[DydxPerpetualOrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_trade_stream: asyncio.Queue = asyncio.Queue()
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()

    @property
    def exchange_name(self) -> str:
        return "dydx"

    async def _track_single_book(self, trading_pair: str):
        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: DydxPerpetualOrderBook = self._order_books[trading_pair]
        while True:
            try:
                message: DydxPerpetualOrderBookMessage = None
                saved_messages: Deque[DydxPerpetualOrderBookMessage] = self._saved_message_queues[trading_pair]
                # Process saved messages first if there are any
                if len(saved_messages) > 0:
                    message = saved_messages.popleft()
                else:
                    message = await message_queue.get()
                if message.type is OrderBookMessageType.DIFF:
                    bids = [ClientOrderBookRow(Decimal(bid["price"]), Decimal(bid["amount"]), message.update_id) for bid in message.bids]
                    asks = [ClientOrderBookRow(Decimal(ask["price"]), Decimal(ask["amount"]), message.update_id) for ask in message.asks]
                    order_book.apply_diffs(bids, asks, int(message.timestamp))

                elif message.type is OrderBookMessageType.SNAPSHOT:
                    bids = [ClientOrderBookRow(Decimal(bid["price"]), Decimal(bid["amount"]), message.update_id) for bid in message.bids]
                    asks = [ClientOrderBookRow(Decimal(ask["price"]), Decimal(ask["amount"]), message.update_id) for ask in message.asks]
                    order_book.apply_snapshot(bids, asks, int(message.timestamp))
                    self.logger().debug("Processed order book snapshot for %s.", trading_pair)

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
