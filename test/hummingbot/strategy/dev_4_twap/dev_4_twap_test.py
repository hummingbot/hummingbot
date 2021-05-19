import time
from unittest import TestCase

from hummingbot.core.clock import (
    Clock,
    ClockMode)

from hummingbot.strategy.dev_4_twap import Dev4TwapTradeStrategy
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

from .dev_4_twap_test_support import MockExchange


class Dev4TwapTradeStrategyTest(TestCase):

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
            Dev4TwapTradeStrategy([])

        self.assertEqual(str(ex_context.exception), "market_infos must not be empty.")

    def test_start(self):
        exchange = MockExchange()
        marketTuple = MarketTradingPairTuple(exchange, "ETH-USDT", "ETH", "USDT")
        strategy = Dev4TwapTradeStrategy(market_infos=[marketTuple])
        strategy.logger().setLevel(1)
        strategy.logger().addHandler(self)

        start_timestamp = time.time()
        strategy.start(Clock(ClockMode.BACKTEST), start_timestamp)

        self.assertTrue(self._is_logged('INFO', 'Waiting for 10.0 to place orders'))

    def test_tick_logs_warning_when_market_not_ready(self):
        exchange = MockExchange()
        exchange.ready = False
        marketTuple = MarketTradingPairTuple(exchange, "ETH-USDT", "ETH", "USDT")
        strategy = Dev4TwapTradeStrategy(market_infos=[marketTuple])
        strategy.logger().setLevel(1)
        strategy.logger().addHandler(self)

        start_timestamp = time.time()
        strategy.start(Clock(ClockMode.BACKTEST), start_timestamp)
        strategy.tick(start_timestamp)

        self.assertTrue(self._is_logged('WARNING', "Markets are not ready. No market making trades are permitted."))

    def test_tick_logs_warning_when_market_not_connected(self):
        exchange = MockExchange()
        exchange.ready = True
        marketTuple = MarketTradingPairTuple(exchange, "ETH-USDT", "ETH", "USDT")
        strategy = Dev4TwapTradeStrategy(market_infos=[marketTuple])
        strategy.logger().setLevel(1)
        strategy.logger().addHandler(self)

        start_timestamp = time.time()
        strategy.start(Clock(ClockMode.BACKTEST), start_timestamp)
        strategy.tick(start_timestamp)

        self.assertTrue(self._is_logged('WARNING',
                                        ("WARNING: Some markets are not connected or are down at the moment. "
                                         "Market making may be dangerous when markets or networks are unstable.")))
