from typing import List, Optional

from hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source import KucoinAPIOrderBookDataSource
from hummingbot.connector.exchange.kucoin.kucoin_auth import KucoinAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker


class KucoinOrderBookTracker(OrderBookTracker):

    def __init__(self,
                 throttler: Optional[AsyncThrottler] = None,
                 trading_pairs: Optional[List[str]] = None,
                 auth: Optional[KucoinAuth] = None):
        super().__init__(KucoinAPIOrderBookDataSource(throttler, trading_pairs, auth), trading_pairs)
