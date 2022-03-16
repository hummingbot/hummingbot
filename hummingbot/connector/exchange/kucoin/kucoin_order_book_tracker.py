import asyncio
from typing import List, Optional

from hummingbot.connector.exchange.kucoin import kucoin_constants as CONSTANTS
from hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source import KucoinAPIOrderBookDataSource
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class KucoinOrderBookTracker(OrderBookTracker):

    def __init__(self,
                 trading_pairs: Optional[List[str]] = None,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None,):
        super().__init__(KucoinAPIOrderBookDataSource(
            trading_pairs=trading_pairs,
            domain=domain,
            api_factory=api_factory,
            throttler=throttler,
            time_synchronizer=time_synchronizer), trading_pairs)
        self._order_book_stream_listener_task: Optional[asyncio.Task] = None

    def start(self):
        """
        Starts the background task that connects to the exchange and listens to order book updates and trade events.
        """
        super().start()
        self._order_book_stream_listener_task = safe_ensure_future(
            self._data_source.listen_for_subscriptions()
        )

    def stop(self):
        """
        Stops the background task
        """
        self._order_book_stream_listener_task and self._order_book_stream_listener_task.cancel()
        super().stop()
