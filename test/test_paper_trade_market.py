#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import unittest

from hummingbot.market.paper_trade.paper_trade_market import PaperTradeMarket, QueuedOrder
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.event.events import OrderType
from hummingbot.market.binance.binance_order_book_tracker import BinanceOrderBookTracker
from hummingbot.core.data_type.limit_order import LimitOrder

from hummingbot.market.paper_trade.symbol_pair import SymbolPair

from typing import (
    Dict,
    List
)


class PaperTradeUnitTest(unittest.TestCase):

    def setUp(self) -> None:
        order_book_tracker = BinanceOrderBookTracker()
        self._paper_trade_market = PaperTradeMarket(order_book_tracker)

    def testPlaceLimitOrders(self):
        self._paper_trade_market.add_symbol_pair(SymbolPair("WETHDAI", "WETH", "DAI"))
        self._paper_trade_market.sell("WETHDAI", 30, OrderType.LIMIT, 100)
        list_limit_orders: List[LimitOrder] = self._paper_trade_market.limit_orders
        first_limit_order: LimitOrder = list_limit_orders[0]
        self.assertEqual(first_limit_order.base_currency, "WETH", msg="Base currency is incorrect")
        self.assertEqual(first_limit_order.quote_currency, "DAI", msg="Quote currency is incorrect")
        self.assertFalse(first_limit_order.is_buy, msg="Limit order is not sell")
        self.assertEqual(first_limit_order.symbol, "WETHDAI", msg="Symbol is incorrect")
        self.assertEqual(first_limit_order.price, 100, msg="Price is incorrect")
        self.assertEqual(first_limit_order.quantity, 30, msg="Quantity is incorrect")
        self.assertEqual(len(list_limit_orders), 1, msg="Limit order did not get added")

        # Change symbol pair to just take in quote and base and output symbols in different ways
        self._paper_trade_market.add_symbol_pair(SymbolPair("BTCBNB", "BTC", "BNB"))
        self._paper_trade_market.buy("BTCBNB", 23, OrderType.LIMIT, 34)
        list_limit_orders: List[LimitOrder] = self._paper_trade_market.limit_orders
        first_limit_order: LimitOrder = list_limit_orders[0]
        self.assertEqual(first_limit_order.base_currency, "BTC", msg="Base currency is incorrect")
        self.assertEqual(first_limit_order.quote_currency, "BNB", msg="Quote currency is incorrect")
        self.assertTrue(first_limit_order.is_buy, msg="Market order is not buy")
        self.assertEqual(first_limit_order.symbol, "BTCBNB", msg="Symbol is incorrect")
        self.assertEqual(first_limit_order.price, 34, msg="Price is incorrect")
        self.assertEqual(first_limit_order.quantity, 23, msg="Quantity is incorrect")
        self.assertEqual(len(list_limit_orders), 2, msg="Limit order did not get added")

    def testMarketOrders(self):
        self._paper_trade_market.add_symbol_pair(SymbolPair("WETHDAI", "WETH", "DAI"))
        self._paper_trade_market.sell("WETHDAI", 30, OrderType.MARKET)
        list_queued_orders: List[QueuedOrder] = self._paper_trade_market.queued_orders
        first_queued_order: QueuedOrder = list_queued_orders[0]
        self.assertFalse(first_queued_order.is_buy, msg="Limit order is not buy")
        self.assertEqual(first_queued_order.symbol, "WETHDAI", msg="Symbol is incorrect")
        self.assertEqual(first_queued_order.amount, 30, msg="Quantity is incorrect")
        self.assertEqual(len(list_queued_orders), 1, msg="Limit order did not get added")

        # Change symbol pair to just take in quote and base and output symbols in different ways
        # Figure out why this test is failing
        self._paper_trade_market.add_symbol_pair(SymbolPair("BTCBNB", "BTC", "BNB"))
        self._paper_trade_market.buy("BTCBNB", 30, OrderType.MARKET)
        list_queued_orders: List[QueuedOrder] = self._paper_trade_market.queued_orders
        first_queued_order: QueuedOrder = list_queued_orders[0]
        self.assertTrue(first_queued_order.is_buy, msg="Market order is not sell")
        self.assertEqual(first_queued_order.symbol, "WETHDAI", msg="Symbol is incorrect")
        self.assertEqual(first_queued_order.amount, 30, msg="Quantity is incorrect")
        self.assertEqual(len(list_queued_orders), 2, msg="Limit order did not get added")
