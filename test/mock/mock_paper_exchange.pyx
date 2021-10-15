from typing import List, Dict, Tuple
import asyncio
from decimal import Decimal

from hummingbot.connector.exchange.paper_trade.paper_trade_exchange cimport PaperTradeExchange
from hummingbot.connector.exchange.paper_trade.trading_pair import TradingPair
from hummingbot.core.event.events import TradeFee
from hummingbot.core.data_type.order_book import OrderBook, OrderBookRow
from hummingbot.core.data_type.composite_order_book cimport CompositeOrderBook
from hummingbot.connector.exchange.paper_trade.market_config import MarketConfig
from hummingbot.client.settings import CONNECTOR_SETTINGS, ConnectorSetting, ConnectorType, TradeFeeType
from .mock_order_tracker import MockOrderTracker


cdef class MockPaperExchange(PaperTradeExchange):

    cdef object c_get_fee(self,
                          str base_asset,
                          str quote_asset,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        return TradeFee(0)

    def __init__(self):
        PaperTradeExchange.__init__(self, MockOrderTracker(), MarketConfig.default_config(), MockPaperExchange)
        CONNECTOR_SETTINGS[self.name] = ConnectorSetting(self.name, ConnectorType.Exchange,
                                                         "", True, False, TradeFeeType.Percent, "",
                                                         [Decimal("0")], None, None, None, None, None)

    @property
    def ready(self):
        return True

    def split_trading_pair(self, trading_pair: str) -> Tuple[str, str]:
        return trading_pair.split("-")

    def set_balanced_order_book(self,
                                str trading_pair,
                                double mid_price,
                                double min_price,
                                double max_price,
                                double price_step_size,
                                double volume_step_size):
        self.c_set_balanced_order_book(trading_pair, mid_price, min_price, max_price, price_step_size, volume_step_size)

    cdef c_set_balanced_order_book(self,
                                   str trading_pair,
                                   double mid_price,
                                   double min_price,
                                   double max_price,
                                   double price_step_size,
                                   double volume_step_size):
        cdef:
            list bids = []
            list asks = []
            double current_price
            double current_size
            CompositeOrderBook order_book
        order_book = CompositeOrderBook()
        current_price = mid_price - price_step_size / 2
        current_size = volume_step_size
        while current_price >= min_price:
            bids.append(OrderBookRow(current_price, current_size, 1))
            current_price -= price_step_size
            current_size += volume_step_size

        current_price = mid_price + price_step_size / 2
        current_size = volume_step_size
        while current_price <= max_price:
            asks.append(OrderBookRow(current_price, current_size, 1))
            current_price += price_step_size
            current_size += volume_step_size

        order_book.apply_snapshot(bids, asks, 1)
        order_book.c_add_listener(self.ORDER_BOOK_TRADE_EVENT_TAG, self._order_book_trade_listener)
        base_asset, quote_asset = self.split_trading_pair(trading_pair)
        self._trading_pairs[trading_pair] = TradingPair(trading_pair, base_asset, quote_asset)
        self.order_book_tracker._order_books[trading_pair] = order_book
