#!/usr/bin/env python

from collections import (
    deque,
    defaultdict
)
import logging
from typing import (
    Deque,
    Dict,
    List,
    Optional
)

from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
)
from hummingbot.core.data_type.order_book_tracker import (
    OrderBookTracker,
    OrderBookTrackerDataSourceType
)
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.market.stablecoinswap.stablecoinswap_blockchain_order_book_data_source import StablecoinswapBlockchainOrderBookDataSource
import hummingbot.market.stablecoinswap.stablecoinswap_contracts as stablecoinswap_contracts


class StablecoinswapOrderBookTracker(OrderBookTracker):
    _stlobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._stlobt_logger is None:
            cls._stlobt_logger = logging.getLogger(__name__)
        return cls._stlobt_logger

    def __init__(self,
                 stl_contract: stablecoinswap_contracts.Stablecoinswap,
                 data_source_type: OrderBookTrackerDataSourceType = OrderBookTrackerDataSourceType.BLOCKCHAIN,
                 symbols: Optional[List[str]] = None):
        super().__init__(data_source_type=data_source_type)
        self._data_source: Optional[OrderBookTrackerDataSource] = None
        self._saved_message_queues: Dict[str, Deque[OrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._stl_contract = stl_contract
        self._symbols: Optional[List[str]] = symbols

    @property
    def data_source(self) -> OrderBookTrackerDataSource:
        if not self._data_source:
            if self._data_source_type is OrderBookTrackerDataSourceType.BLOCKCHAIN:
                self._data_source = StablecoinswapBlockchainOrderBookDataSource(
                    symbols=self._symbols, stl_contract=self._stl_contract)
            else:
                raise ValueError(f"data_source_type {self._data_source_type} is not supported.")
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "stablecoinswap"

    async def start(self):
        self._order_book_snapshot_listener_task = safe_ensure_future(
            self.data_source.listen_for_order_book_snapshots(self._ev_loop, self._order_book_snapshot_stream)
        )
        self._refresh_tracking_task = safe_ensure_future(
            self._refresh_tracking_loop()
        )
        self._order_book_snapshot_router_task = safe_ensure_future(
            self._order_book_snapshot_router()
        )
