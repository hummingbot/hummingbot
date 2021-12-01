import unittest
from decimal import Decimal
from hummingbot.strategy.triangular_arbitrage.model.model_book import ModelBook
from hummingbot.core.data_type.order_book_row import ClientOrderBookRow


class TestModelBook(unittest.TestCase):
    _level_size = 5

    def setUp(self):
        self.left_trading_pair = "WBTC-USDT"
        self.cross_trading_pair = "WBTC-USDC"
        self.right_trading_pair = "USDC-USDT"

        # left_edge, wbtc_usdt
        self.book_left_edge = ModelBook(
            bids=[
                ClientOrderBookRow(Decimal("62675.76"), Decimal("0.043"), 0),
                ClientOrderBookRow(Decimal("62655.84"), Decimal("0.102"), 0),
                ClientOrderBookRow(Decimal("62616.01"), Decimal("0.102"), 0),
                ClientOrderBookRow(Decimal("62596.09"), Decimal("0.306"), 0),
                ClientOrderBookRow(Decimal("62576.18"), Decimal("0.204"), 0),
                ClientOrderBookRow(Decimal("62536.35"), Decimal("0.204"), 0),
            ],
            asks=[
                ClientOrderBookRow(Decimal("63244.63"), Decimal("0.100"), 0),
                ClientOrderBookRow(Decimal("63247.27"), Decimal("0.050"), 0),
                ClientOrderBookRow(Decimal("63367.34"), Decimal("0.175"), 0),
                ClientOrderBookRow(Decimal("63490.06"), Decimal("0.189"), 0),
                ClientOrderBookRow(Decimal("63613.33"), Decimal("0.200"), 0),
                ClientOrderBookRow(Decimal("63736.95"), Decimal("0.230"), 0),
            ],
            level_size=self._level_size)

        # cross_edge, wbtc-usdc
        self.book_cross_edge = ModelBook(
            bids=[
                ClientOrderBookRow(Decimal("62730.23"), Decimal("0.029"), 0),
                ClientOrderBookRow(Decimal("62690.41"), Decimal("0.017"), 0),
                ClientOrderBookRow(Decimal("62670.50"), Decimal("0.023"), 0),
                ClientOrderBookRow(Decimal("62650.95"), Decimal("0.050"), 0),
                ClientOrderBookRow(Decimal("62270.15"), Decimal("0.100"), 0),
                ClientOrderBookRow(Decimal("62128.01"), Decimal("0.037"), 0),
            ],
            asks=[
                ClientOrderBookRow(Decimal("62777.92"), Decimal("0.025"), 0),
                ClientOrderBookRow(Decimal("62898.93"), Decimal("0.076"), 0),
                ClientOrderBookRow(Decimal("63020.46"), Decimal("0.095"), 0),
                ClientOrderBookRow(Decimal("63142.36"), Decimal("0.100"), 0),
                ClientOrderBookRow(Decimal("63278.41"), Decimal("0.032"), 0),
                ClientOrderBookRow(Decimal("63350.21"), Decimal("0.075"), 0),
            ],
            level_size=self._level_size)

        # right edge, usdc-usdt
        self.book_right_edge = ModelBook(
            bids=[
                ClientOrderBookRow(Decimal("0.9950"), Decimal("11890212"), 0),
                ClientOrderBookRow(Decimal("0.9901"), Decimal("26851827"), 0),
                ClientOrderBookRow(Decimal("0.9900"), Decimal("20000000"), 0),
                ClientOrderBookRow(Decimal("0.9896"), Decimal("35000000"), 0),
                ClientOrderBookRow(Decimal("0.9890"), Decimal("12000000"), 0),
                ClientOrderBookRow(Decimal("0.9885"), Decimal("16000000"), 0),
            ],
            asks=[
                ClientOrderBookRow(Decimal("1.0000"), Decimal("66372257"), 0),
                ClientOrderBookRow(Decimal("1.0001"), Decimal("134258650"), 0),
                ClientOrderBookRow(Decimal("1.0002"), Decimal("81948050"), 0),
                ClientOrderBookRow(Decimal("1.0003"), Decimal("4234959"), 0),
                ClientOrderBookRow(Decimal("1.0005"), Decimal("106018040"), 0),
                ClientOrderBookRow(Decimal("1.0006"), Decimal("24223459"), 0),
            ],
            level_size=self._level_size)

    def test_level_size(self):
        self.assertEqual(len(self.book_left_edge.bids), self._level_size)
        self.assertEqual(len(self.book_left_edge.asks), self._level_size)

    def test_best_price(self):
        self.assertEqual(self.book_left_edge.bids[0].price, Decimal("62675.76"))
        self.assertEqual(self.book_left_edge.asks[0].price, Decimal("63244.63"))
