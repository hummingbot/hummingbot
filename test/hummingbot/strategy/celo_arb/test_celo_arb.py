#!/usr/bin/env python
from decimal import Decimal
import logging
import pandas as pd
import unittest
import mock
from nose.plugins.attrib import attr
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
from test.connector.fixture_celo import outputs as celo_outputs, TEST_ADDRESS, TEST_PASSWORD
from hummingbot.connector.other.celo.celo_cli import CeloCLI
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from test.mock.mock_paper_exchange import MockPaperExchange

logging.basicConfig(level=logging.ERROR)

MOCK_CELO_COMMANDS = True


def mock_command(commands):
    commands = tuple(commands)
    print(f"command: {commands}")
    print(f"output: {celo_outputs[commands]}")
    return celo_outputs[commands]


@attr('stable')
class CeloArbUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair = "CELO-CUSD"
    base_asset = trading_pair.split("-")[0]
    quote_asset = trading_pair.split("-")[1]

    @classmethod
    def setUpClass(cls):
        if MOCK_CELO_COMMANDS:
            cls._patcher = mock.patch("hummingbot.connector.other.celo.celo_cli.command")
            cls._mock = cls._patcher.start()
            cls._mock.side_effect = mock_command

    @classmethod
    def tearDownClass(cls) -> None:
        if MOCK_CELO_COMMANDS:
            cls._patcher.stop()

    def setUp(self):
        self.maxDiff = None
        self.clock: Clock = Clock(ClockMode.BACKTEST, 1.0, self.start_timestamp, self.end_timestamp)
        self.market: MockPaperExchange = MockPaperExchange()

        self.market.set_balanced_order_book(self.trading_pair, 10, 5, 15, 0.1, 1)

        self.market.set_balance(self.base_asset, 500)
        self.market.set_balance(self.quote_asset, 500)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 5, 5, 5, 5
            )
        )
        self.market_info = MarketTradingPairTuple(self.market, self.trading_pair,
                                                  self.base_asset, self.quote_asset)
        self.logging_options: int = CeloArbStrategy.OPTION_LOG_ALL
        self.strategy = CeloArbStrategy()
        self.strategy.init_params(
            self.market_info,
            min_profitability=Decimal("0.01"),
            order_amount=Decimal("1"),
            celo_slippage_buffer=Decimal("0.001"),
            logging_options=self.logging_options,
            hb_app_notification=False,
            mock_celo_cli_mode=True
        )
        self.clock.add_iterator(self.market)
        self.clock.add_iterator(self.strategy)
        self.market_order_fill_logger: EventLogger = EventLogger()
        self.market.add_listener(MarketEvent.OrderFilled, self.market_order_fill_logger)
        CeloCLI.unlock_account(TEST_ADDRESS, TEST_PASSWORD)

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
        # Sell price at CTP (counter party) 1 CELO is 9.95 CUSD
        # At Celo 9.95 CUSD will get you 1 CELO, so the profit is 0%
        celo_buy_trade = trade_profits[0]
        self.assertTrue(celo_buy_trade.is_celo_buy)
        # Can sell at CTP at 9.9499
        self.assertEqual(celo_buy_trade.ctp_price, Decimal("9.9499"))
        # Can buy at celo for 9.95
        self.assertEqual(celo_buy_trade.celo_price, Decimal("9.95"))
        # profit is almost 0
        self.assertAlmostEqual(celo_buy_trade.profit, Decimal('-0.00001005'))

        # Buy price at CTP (counter party) 1 CELO at 10.05 USD
        # at Celo 1 CELO will get you 10.5 USD, so the profit is (10.5 - 10.05)/10.05 = 0.0447761194
        celo_sell_trade = trade_profits[1]
        self.assertFalse(celo_sell_trade.is_celo_buy)
        # Can buy price at CTP for 10.05
        self.assertEqual(celo_sell_trade.ctp_price, Decimal("10.05"))
        # vwap price is 10.05
        self.assertEqual(celo_sell_trade.ctp_vwap, Decimal("10.05"))
        # Can sell price celo at 10.w
        self.assertEqual(celo_sell_trade.celo_price, Decimal("10.5"))
        self.assertAlmostEqual(celo_sell_trade.profit, Decimal("0.0447761194"))

        order_amount = 5
        trade_profits = get_trade_profits(self.market, self.trading_pair, order_amount)

        celo_buy_trade = trade_profits[0]
        self.assertTrue(celo_buy_trade.is_celo_buy)
        # VWAP Sell price (5 CELO) at CTP is ((9.95 * 1) + (9.85 * 2) + (9.75 * 2))/5 = 9.83
        self.assertEqual(celo_buy_trade.ctp_vwap, Decimal("9.83"))
        self.assertEqual(celo_buy_trade.ctp_price, Decimal("9.75"))
        # for 9.83 * 5 USD, you can get 0.99 * 5 CELO at Celo, so the price is 9.83/0.99 = 9.92929292929
        self.assertAlmostEqual(celo_buy_trade.celo_price, Decimal("9.92929292929"))
        # profit is -0.00999999999
        self.assertAlmostEqual(celo_buy_trade.profit, Decimal("-0.00999999999"))

        celo_sell_trade = trade_profits[1]
        self.assertFalse(celo_sell_trade.is_celo_buy)
        # VWAP Buy price (5 CELO) at CTP is ((10.05 * 1) + (10.15 * 2) + (10.25 * 2))/5 = 10.169
        self.assertEqual(celo_sell_trade.ctp_vwap, Decimal("10.169"))
        self.assertEqual(celo_sell_trade.ctp_price, Decimal("10.25"))
        # Can sell price celo at 10.1 each
        self.assertEqual(celo_sell_trade.celo_price, Decimal("10.1"))
        # profit = (10.1 - 10.17)/10.17 = -0.00678532795
        self.assertAlmostEqual(celo_sell_trade.profit, Decimal("-0.00678532795"))

    def test_profitable_celo_sell_trade(self):
        order_amount = Decimal("1")
        self.strategy.order_amount = order_amount
        trade_profits = get_trade_profits(self.market, self.trading_pair, order_amount)
        celo_sell_trade = [t for t in trade_profits if not t.is_celo_buy][0]
        self.clock.backtest_til(self.start_timestamp + 1)
        ctp_active_orders = self.strategy.market_info_to_active_orders[self.market_info]
        self.assertEqual(len(ctp_active_orders), 1)
        self.assertTrue(ctp_active_orders[0].is_buy)
        self.assertEqual(ctp_active_orders[0].price, celo_sell_trade.ctp_price)
        self.assertEqual(ctp_active_orders[0].quantity, order_amount)
        self.assertEqual(len(self.strategy.celo_orders), 1)
        self.assertFalse(self.strategy.celo_orders[0].is_buy)
        self.assertEqual(self.strategy.celo_orders[0].price, celo_sell_trade.celo_price)
        self.assertEqual(self.strategy.celo_orders[0].amount, order_amount)

    def test_profitable_celo_buy_trade(self):
        order_amount = Decimal("2")
        self.strategy.order_amount = order_amount
        trade_profits = get_trade_profits(self.market, self.trading_pair, order_amount)
        celo_buy_trade = [t for t in trade_profits if t.is_celo_buy][0]
        self.clock.backtest_til(self.start_timestamp + 1)
        ctp_active_orders = self.strategy.market_info_to_active_orders[self.market_info]
        self.assertEqual(len(ctp_active_orders), 1)
        self.assertFalse(ctp_active_orders[0].is_buy)
        self.assertEqual(ctp_active_orders[0].price, celo_buy_trade.ctp_price)
        self.assertEqual(ctp_active_orders[0].quantity, order_amount)
        self.assertEqual(len(self.strategy.celo_orders), 1)
        self.assertTrue(self.strategy.celo_orders[0].is_buy)
        self.assertEqual(self.strategy.celo_orders[0].price, celo_buy_trade.celo_price)
        self.assertEqual(self.strategy.celo_orders[0].amount, order_amount)

    def test_profitable_but_insufficient_balance(self):
        order_amount = Decimal("2")
        trade_profits = get_trade_profits(self.market, self.trading_pair, order_amount)
        celo_buy_trade = [t for t in trade_profits if t.is_celo_buy][0]
        self.assertTrue(celo_buy_trade.profit > self.strategy.min_profitability)
        self.market.set_balance(self.base_asset, 1)
        self.market.set_balance(self.quote_asset, 1)
        self.strategy.order_amount = order_amount
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(len(self.strategy.market_info_to_active_orders), 0)
        self.assertEqual(len(self.strategy.celo_orders), 0)

    def test_no_profitable_trade(self):
        order_amount = 5
        trade_profits = get_trade_profits(self.market, self.trading_pair, order_amount)
        profitables = [t for t in trade_profits if t.profit >= self.strategy.min_profitability]
        self.assertEqual(len(profitables), 0)
        self.strategy.order_amount = order_amount
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(len(self.strategy.market_info_to_active_orders), 0)
        self.assertEqual(len(self.strategy.celo_orders), 0)
