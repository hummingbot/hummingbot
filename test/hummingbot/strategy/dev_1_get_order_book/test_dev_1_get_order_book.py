
import asyncio
import unittest
import pandas as pd

from decimal import Decimal

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.strategy.dev_1_get_order_book import GetOrderBookStrategy
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from test.mock.mock_paper_exchange import MockPaperExchange


class Dev1GetOrderBookUnitTest(unittest.TestCase):

    start_timestamp: float = pd.Timestamp("2019-01-01", tz="UTC").timestamp()
    end_timestamp: float = pd.Timestamp("2019-01-01 01:00:00", tz="UTC").timestamp()
    tick_size: int = 10

    trading_pair: str = "COINALPHA-HBOT"
    base_asset, quote_asset = trading_pair.split("-")

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()
        cls.clock: Clock = Clock(ClockMode.BACKTEST, cls.tick_size, cls.start_timestamp, cls.end_timestamp)
        cls.market: MockPaperExchange = MockPaperExchange()
        cls.strategy: GetOrderBookStrategy = GetOrderBookStrategy(
            exchange=cls.market,
            trading_pair=cls.trading_pair,
        )

    def test_market_not_ready(self):
        self.clock.add_iterator(self.strategy)
        self.clock.add_iterator(self.market)
        # Check status output when market is not ready
        expected_msg: str = "Exchange connector(s) are not ready."
        status_msg_output: str = self.ev_loop.run_until_complete(self.strategy.format_status())
        self.assertEqual(expected_msg, status_msg_output)

    def test_market_ready(self):
        # Simulate Order Book being populated
        quote_balance = 5000

        self.mid_price = 100
        self.time_delay = 15
        self.cancel_order_wait_time = 45
        self.market.set_balanced_order_book(trading_pair=self.trading_pair,
                                            mid_price=self.mid_price,
                                            min_price=1,
                                            max_price=200,
                                            price_step_size=1,
                                            volume_step_size=10)
        self.market.set_balance("COINALPHA", 500)
        self.market.set_balance("HBOT", quote_balance)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 6, 6, 6, 6
            )
        )

        expected_best_ask = min([row.price for row in self.market.order_book_ask_entries(self.trading_pair)])
        expected_best_bid = max([row.price for row in self.market.order_book_bid_entries(self.trading_pair)])

        self.clock.add_iterator(self.market)
        self.clock.add_iterator(self.strategy)

        self.clock.backtest_til(self.start_timestamp + self.tick_size)

        # Check status output when market is ready
        status_msg_output: str = self.ev_loop.run_until_complete(self.strategy.format_status())
        curr_best_bid, curr_best_ask = [Decimal(item) for item in status_msg_output.split('\n')[2].split(' ') if item != '']
        self.assertEqual(expected_best_bid, curr_best_bid)
        self.assertEqual(expected_best_ask, curr_best_ask)
