import asyncio
import unittest

import pandas as pd

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.strategy.dev_0_hello_world import HelloWorldStrategy


class Dev0HelloWorldUnitTest(unittest.TestCase):

    start_timestamp: float = pd.Timestamp("2019-01-01", tz="UTC").timestamp()
    end_timestamp: float = pd.Timestamp("2019-01-01 01:00:00", tz="UTC").timestamp()
    tick_size: int = 10

    trading_pair: str = "COINALPHA-HBOT"
    base_asset, quote_asset = trading_pair.split("-")

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()
        cls.clock: Clock = Clock(ClockMode.BACKTEST, cls.tick_size, cls.start_timestamp, cls.end_timestamp)
        cls.market: MockPaperExchange = MockPaperExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap())
        )
        cls.strategy: HelloWorldStrategy = HelloWorldStrategy(
            exchange=cls.market,
            trading_pair=cls.trading_pair,
            asset=cls.quote_asset,
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
                                            mid_price=self.mid_price, min_price=1,
                                            max_price=200, price_step_size=1, volume_step_size=10)
        self.market.set_balance("COINALPHA", 500)
        self.market.set_balance("HBOT", quote_balance)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 6, 6, 6, 6
            )
        )

        self.clock.add_iterator(self.market)
        self.clock.add_iterator(self.strategy)

        self.clock.backtest_til(self.start_timestamp + self.tick_size)

        # Check status output when market is ready
        status_msg_output: str = self.ev_loop.run_until_complete(self.strategy.format_status())
        self.assertTrue("Assets:" in status_msg_output)
        self.assertTrue(f"HBOT    {quote_balance}" in status_msg_output)
