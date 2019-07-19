#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import unittest

from hummingbot.market.paper_trade.paper_trade_market import PaperTradeMarket
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.event.events import OrderType
from hummingbot.market.binance.binance_order_book_tracker import BinanceOrderBookTracker

from hummingbot.market.paper_trade.symbol_pair import SymbolPair


class MarketSimulatorMarketOrderUnitTest(unittest.TestCase):

    def setUp(self) -> None:
        order_book_tracker = BinanceOrderBookTracker()
        self._paper_trade_market = PaperTradeMarket(order_book_tracker)

    def testSellMarket(self):
        self._paper_trade_market.add_symbol_pair(SymbolPair("WETHDAI", "WETH", "DAI"))
        self._paper_trade_market.buy("WETHDAI", 30, OrderType.LIMIT, 100)
        list_limit_orders = self._paper_trade_market.limit_orders()
        self.assertEqual(len(list_limit_orders), 2, msg="Limit order did not get added")
