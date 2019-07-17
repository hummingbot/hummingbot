import unittest
from hummingbot.market.paper_trade.paper_trade_market import PaperTradeMarket
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.market.binance.binance_order_book_tracker import BinanceOrderBookTracker

class MarketSimulatorMarketOrderUnitTest(unittest.TestCase):

    def setUp(self) -> None:
        order_book_tracker = BinanceOrderBookTracker()
        self.paper_trade_market = PaperTradeMarket(order_book_tracker)

    def testSellMarket(self):
        