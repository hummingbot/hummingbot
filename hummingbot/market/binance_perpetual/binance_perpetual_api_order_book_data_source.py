import asyncio
from typing import Dict, List

import pandas as pd

from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry


class BinancePerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):
    @classmethod
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        raise NotImplementedError

    async def get_trading_pairs(self) -> List[str]:
        raise NotImplementedError

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        raise NotImplementedError

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        raise NotImplementedError

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        raise NotImplementedError

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        raise NotImplementedError
