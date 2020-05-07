#!/usr/bin/env python
from decimal import Decimal
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
import unittest
import mock

from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import (
    QuantizationParams
)
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent
)
from hummingbot.strategy.celo_arb.celo_arb import CeloArbStrategy, get_trade_profits
from test.integration.assets.mock_data.fixture_celo import outputs as celo_outputs


MOCK_CELO_COMMANDS = True


def mock_command(commands):
    commands = tuple(commands)
    return celo_outputs[commands]


class CeloArbUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair = "CGLD-CUSD"
    base_asset = trading_pair.split("-")[0]
    quote_asset = trading_pair.split("-")[1]

    @classmethod
    def setUpClass(cls):
        if MOCK_CELO_COMMANDS:
            cls._patcher = mock.patch("hummingbot.market.celo.celo_cli.command")
            cls._mock = cls._patcher.start()
            cls._mock.side_effect = mock_command

    @classmethod
    def tearDownClass(cls) -> None:
        if MOCK_CELO_COMMANDS:
            cls._patcher.stop()

    def setUp(self):
        self.maxDiff = None
        self.clock: Clock = Clock(ClockMode.BACKTEST, 1.0, self.start_timestamp, self.end_timestamp)
        self.market: BacktestMarket = BacktestMarket()

        self.market_data = MockOrderBookLoader(self.trading_pair, self.base_asset, self.quote_asset)
        self.market_data.set_balanced_order_book(10, 5, 15, 0.1, 1)

        self.market.add_data(self.market_data)

        self.market.set_balance(self.base_asset, 500)
        self.market.set_balance(self.quote_asset, 500)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 5, 5, 5, 5
            )
        )
        self.market_trading_pair_tuple = MarketTradingPairTuple(self.market, self.trading_pair,
                                                                self.base_asset, self.quote_asset)

        self.logging_options: int = CeloArbStrategy.OPTION_LOG_ALL

        self.strategy = CeloArbStrategy(
            self.market_trading_pair_tuple,
            min_profitability=Decimal("0.03"),
            order_amount=Decimal("100"),
            logging_options=self.logging_options
        )

        self.clock.add_iterator(self.market)
        self.clock.add_iterator(self.strategy)

        self.market_order_fill_logger: EventLogger = EventLogger()

        self.market.add_listener(MarketEvent.OrderFilled, self.market_order_fill_logger)

    def test_get_trade_profits(self):
        """
        Order book bids
            price  amount  update_id
        0    9.95       1          1
        1    9.85       2          1
        2    9.75       3          1
        3    9.65       4          1
        4    9.55       5          1
        Order book asks
            price  amount  update_id
        0   10.05       1          1
        1   10.15       2          1
        2   10.25       3          1
        3   10.35       4          1
        4   10.45       5          1
        """
        order_amount = 1
        trade_profits = get_trade_profits(self.market, self.trading_pair, order_amount)
        # Sell price at CTP (counter party) 1 CGLD is 9.95 CUSD
        # At Celo 9.95 CUSD will get you 1 CGLD, so the profit is 0%
        celo_buy_trade = trade_profits[0]
        self.assertTrue(celo_buy_trade[0])
        # Can sell at CTP at 9.95
        self.assertEqual(celo_buy_trade[1], Decimal("9.95"))
        # Can buy at celo for 9.95
        self.assertEqual(celo_buy_trade[2], Decimal("9.95"))
        # profit is 0
        self.assertEqual(celo_buy_trade[3], Decimal("0"))

        # Buy price at CTP (counter party) 1 CGLD at 10.05 USD
        # at Celo 1 CGLD will get you 11 USD, so the profit is (10.1 - 10.05)/10.05 = 0.00497512437
        celo_sell_trade = trade_profits[1]
        self.assertFalse(celo_sell_trade[0])
        # Can buy price at CTP for 10.05
        self.assertEqual(celo_sell_trade[1], Decimal("10.05"))
        # Can sell price celo at 10.1
        self.assertEqual(celo_sell_trade[2], Decimal("10.1"))
        self.assertAlmostEqual(celo_sell_trade[3], Decimal("0.00497512437"))

        order_amount = 5
        trade_profits = get_trade_profits(self.market, self.trading_pair, order_amount)

        celo_buy_trade = trade_profits[0]
        self.assertTrue(celo_buy_trade[0])
        # VWAP Sell price (5 CGLD) at CTP is ((9.95 * 1) + (9.85 * 2) + (9.75 * 5))/5 = 9.83
        self.assertEqual(celo_buy_trade[1], Decimal("9.83"))
        # for 9.83 * 5 USD, you can get 0.99 * 5 CGLD at Celo, so the price is 9.83/0.99 = 9.92929292929
        self.assertAlmostEqual(celo_buy_trade[2], Decimal("9.92929292929"))
        # profit is -0.00999999999
        self.assertAlmostEqual(celo_buy_trade[3], Decimal("-0.00999999999"))

        celo_sell_trade = trade_profits[1]
        self.assertFalse(celo_sell_trade[0])
        # VWAP Buy price (5 CGLD) at CTP is ((10.05 * 1) + (10.15 * 2) + (10.25 * 2))/5 = 10.17
        self.assertEqual(celo_sell_trade[1], Decimal("10.17"))
        # Can sell price celo at 10.1 each
        self.assertEqual(celo_sell_trade[2], Decimal("10.1"))
        # profit = (10.1 - 10.17)/10.17 = -0.00688298918
        self.assertAlmostEqual(celo_sell_trade[3], Decimal("-0.00688298918"))
