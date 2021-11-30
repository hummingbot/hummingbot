# distutils: language=c++

from typing import List
from hummingbot.core.data_type.order_book_row import ClientOrderBookRow

cdef class ModelBook:
    def __init__(self,
                 bids: List[ClientOrderBookRow] = [],
                 asks: List[ClientOrderBookRow] = [],
                 level_size: int = 5
                 ):
        self.bids = bids
        self.asks = asks
        self._level_size = level_size
        self._normalize()

    def _normalize(self):
        self.bids.sort(key=lambda bid: bid.price, reverse=True)
        self.asks.sort(key=lambda ask: ask.price, reverse=False)
        if len(self.bids) > self._level_size:
            self.bids = self.bids[:self._level_size]
        if len(self.asks) > self._level_size:
            self.asks = self.asks[:self._level_size]
