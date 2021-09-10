import time
from decimal import Decimal
from datetime import datetime
from unittest import TestCase

from hummingbot.core.clock import (
    Clock,
    ClockMode)
from hummingbot.strategy.conditional_execution_state import RunInTimeConditionalExecutionState

from hummingbot.strategy.twap import TwapTradeStrategy
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

from test.hummingbot.strategy.twap.twap_test_support import MockExchange


class TwapTradeStrategyTest(TestCase):

    level = 0
    log_records = []

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def test_creation_without_market_info_fails(self):
        with self.assertRaises(ValueError) as ex_context:
            TwapTradeStrategy([])

        self.assertEqual(str(ex_context.exception), "market_infos must not be empty.")

    def test_start(self):
        exchange = MockExchange()
        marketTuple = MarketTradingPairTuple(exchange, "ETH-USDT", "ETH", "USDT")
        strategy = TwapTradeStrategy(market_infos=[marketTuple])
        strategy.logger().setLevel(1)
        strategy.logger().addHandler(self)

        start_timestamp = time.time()
        strategy.start(Clock(ClockMode.BACKTEST), start_timestamp)

        self.assertTrue(self._is_logged('INFO', 'Waiting for 10.0 to place orders'))

    def test_tick_logs_warning_when_market_not_ready(self):
        exchange = MockExchange()
        exchange.ready = False
        marketTuple = MarketTradingPairTuple(exchange, "ETH-USDT", "ETH", "USDT")
        strategy = TwapTradeStrategy(market_infos=[marketTuple])
        strategy.logger().setLevel(1)
        strategy.logger().addHandler(self)

        start_timestamp = time.time()
        strategy.start(Clock(ClockMode.BACKTEST), start_timestamp)
        strategy.tick(start_timestamp + 1000)

        self.assertTrue(self._is_logged('WARNING', "Markets are not ready. No market making trades are permitted."))

    def test_tick_logs_warning_when_market_not_connected(self):
        exchange = MockExchange()
        exchange.ready = True
        marketTuple = MarketTradingPairTuple(exchange, "ETH-USDT", "ETH", "USDT")
        strategy = TwapTradeStrategy(market_infos=[marketTuple])
        strategy.logger().setLevel(1)
        strategy.logger().addHandler(self)

        start_timestamp = time.time()
        strategy.start(Clock(ClockMode.BACKTEST), start_timestamp)
        strategy.tick(start_timestamp + 1000)

        self.assertTrue(self._is_logged('WARNING',
                                        ("WARNING: Some markets are not connected or are down at the moment. "
                                         "Market making may be dangerous when markets or networks are unstable.")))

    def test_status(self):
        exchange = MockExchange()
        exchange.buy_price = Decimal("25100")
        exchange.sell_price = Decimal("24900")
        exchange.update_account_balance({"ETH": Decimal("100000"), "USDT": Decimal(10000)})
        exchange.update_account_available_balance({"ETH": Decimal("100000"), "USDT": Decimal(10000)})
        marketTuple = MarketTradingPairTuple(exchange, "ETH-USDT", "ETH", "USDT")
        strategy = TwapTradeStrategy(market_infos=[marketTuple],
                                     is_buy=True,
                                     target_asset_amount=Decimal(100),
                                     order_step_size=Decimal(10),
                                     order_price=Decimal(25000))

        status = strategy.format_status()
        expected_status = ("\n  Configuration:\n"
                           "    Total amount: 100 ETH    Order price: 25000 USDT    Order size: 10.00 ETH\n"
                           "    Execution type: run continuously\n\n"
                           "  Markets:\n"
                           "           Exchange    Market  Best Bid Price  Best Ask Price  Mid Price\n"
                           "    0  MockExchange  ETH-USDT           24900           25100      25000\n\n"
                           "  Assets:\n"
                           "           Exchange Asset  Total Balance  Available Balance\n"
                           "    0  MockExchange   ETH         100000             100000\n"
                           "    1  MockExchange  USDT          10000              10000\n\n"
                           "  No active maker orders.\n\n"
                           "  Average filled orders price: 0 USDT\n"
                           "  Pending amount: 100 ETH\n\n"
                           "*** WARNINGS ***\n"
                           "  Markets are offline for the ETH-USDT pair. "
                           "Continued trading with these markets may be dangerous.\n")

        self.assertEqual(expected_status, status)

    def test_status_with_time_span_execution(self):
        exchange = MockExchange()
        exchange.buy_price = Decimal("25100")
        exchange.sell_price = Decimal("24900")
        exchange.update_account_balance({"ETH": Decimal("100000"), "USDT": Decimal(10000)})
        exchange.update_account_available_balance({"ETH": Decimal("100000"), "USDT": Decimal(10000)})
        marketTuple = MarketTradingPairTuple(exchange, "ETH-USDT", "ETH", "USDT")
        start_time_string = "2021-06-24 10:00:00"
        end_time_string = "2021-06-24 10:30:00"
        execution_type = RunInTimeConditionalExecutionState(start_timestamp=datetime.fromisoformat(start_time_string),
                                                            end_timestamp=datetime.fromisoformat(end_time_string))
        strategy = TwapTradeStrategy(market_infos=[marketTuple],
                                     is_buy=True,
                                     target_asset_amount=Decimal(100),
                                     order_step_size=Decimal(10),
                                     order_price=Decimal(25000),
                                     execution_state=execution_type)

        status = strategy.format_status()
        expected_status = ("\n  Configuration:\n"
                           "    Total amount: 100 ETH    Order price: 25000 USDT    Order size: 10.00 ETH\n"
                           f"    Execution type: run between {start_time_string} and {end_time_string}\n\n"
                           "  Markets:\n"
                           "           Exchange    Market  Best Bid Price  Best Ask Price  Mid Price\n"
                           "    0  MockExchange  ETH-USDT           24900           25100      25000\n\n"
                           "  Assets:\n"
                           "           Exchange Asset  Total Balance  Available Balance\n"
                           "    0  MockExchange   ETH         100000             100000\n"
                           "    1  MockExchange  USDT          10000              10000\n\n"
                           "  No active maker orders.\n\n"
                           "  Average filled orders price: 0 USDT\n"
                           "  Pending amount: 100 ETH\n\n"
                           "*** WARNINGS ***\n"
                           "  Markets are offline for the ETH-USDT pair. "
                           "Continued trading with these markets may be dangerous.\n")

        self.assertEqual(expected_status, status)

    def test_status_with_delayed_start_execution(self):
        exchange = MockExchange()
        exchange.buy_price = Decimal("25100")
        exchange.sell_price = Decimal("24900")
        exchange.update_account_balance({"ETH": Decimal("100000"), "USDT": Decimal(10000)})
        exchange.update_account_available_balance({"ETH": Decimal("100000"), "USDT": Decimal(10000)})
        marketTuple = MarketTradingPairTuple(exchange, "ETH-USDT", "ETH", "USDT")
        start_time_string = "2021-06-24 10:00:00"
        execution_type = RunInTimeConditionalExecutionState(start_timestamp=datetime.fromisoformat(start_time_string))
        strategy = TwapTradeStrategy(market_infos=[marketTuple],
                                     is_buy=True,
                                     target_asset_amount=Decimal(100),
                                     order_step_size=Decimal(10),
                                     order_price=Decimal(25000),
                                     execution_state=execution_type)

        status = strategy.format_status()
        expected_status = ("\n  Configuration:\n"
                           "    Total amount: 100 ETH    Order price: 25000 USDT    Order size: 10.00 ETH\n"
                           f"    Execution type: run from {start_time_string}\n\n"
                           "  Markets:\n"
                           "           Exchange    Market  Best Bid Price  Best Ask Price  Mid Price\n"
                           "    0  MockExchange  ETH-USDT           24900           25100      25000\n\n"
                           "  Assets:\n"
                           "           Exchange Asset  Total Balance  Available Balance\n"
                           "    0  MockExchange   ETH         100000             100000\n"
                           "    1  MockExchange  USDT          10000              10000\n\n"
                           "  No active maker orders.\n\n"
                           "  Average filled orders price: 0 USDT\n"
                           "  Pending amount: 100 ETH\n\n"
                           "*** WARNINGS ***\n"
                           "  Markets are offline for the ETH-USDT pair. "
                           "Continued trading with these markets may be dangerous.\n")

        self.assertEqual(expected_status, status)
