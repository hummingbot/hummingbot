#!/usr/bin/env python

from typing import List

from wings.order_book_tracker import OrderBookTracker, BinanceOrderBook


class PriceCalculator:
    def __init__(self, order_book_tracker: OrderBookTracker):
        self._order_book_tracker: OrderBookTracker = order_book_tracker

    def get_price(self, base_asset: str, quote_asset: str) -> float:
        symbol: str = f"{base_asset}{quote_asset}"
        return self.get_price_from_symbol(symbol)

    def get_price_from_symbol(self, symbol: str) -> float:
        order_book: BinanceOrderBook = self._order_book_tracker.order_books[symbol]
        buy_price: float = order_book.get_price(True)
        return buy_price

    @property
    def order_book_tracker(self) -> OrderBookTracker:
        return self._order_book_tracker

    @property
    def symbols(self) -> List[str]:
        return list(self._order_book_tracker.order_books.keys())
