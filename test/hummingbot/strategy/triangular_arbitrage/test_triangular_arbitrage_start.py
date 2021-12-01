import unittest
from unittest.mock import patch
from typing import List, Tuple
from decimal import Decimal
import hummingbot.strategy.triangular_arbitrage.start as strategy_start
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.triangular_arbitrage.triangular_arbitrage_config_map import (
    triangular_arbitrage_config_map as c_map
)
from test.hummingbot.strategy import assign_config_default


def side_effect(exchange, source, target):
    return (f"{source}-{target}", "forward")


class TriangularArbitrageStartTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.strategy = None
        self.markets = {"binance": ExchangeBase()}
        self.log_errors = []
        assign_config_default(c_map)
        c_map.get("exchange").value = "binance"
        c_map.get("target_currency").value = 'ETH'
        c_map.get("first_aux_currency").value = 'BTC'
        c_map.get("second_aux_currency").value = 'USDT'
        c_map.get("min_profitability").value = Decimal(0.3)

    def _initialize_market_assets(self, market, trading_pairs):
        market_trading_pairs: List[Tuple[str, str]] = [(trading_pair.split('-')) for trading_pair in trading_pairs]
        return market_trading_pairs

    def _initialize_markets(self, market_names):
        pass

    def _initialize_wallet(self, token_trading_pairs: List[str]):
        pass

    def _notify(self, msg):
        pass

    def logger(self):
        return self

    def error(self, message, exc_info):
        self.log_errors.append(message)

    @patch('hummingbot.strategy.triangular_arbitrage.start.infer_market_trading_pair')
    def test_strategy_creation(self, mock_inference):
        mock_inference.side_effect = side_effect
        strategy_start.start(self)
        self.assertEqual(self.strategy.triangular_arbitrage_module.min_profitability, Decimal(0.3) / Decimal(100))
        self.assertEqual(self.strategy.triangular_arbitrage_module.ccw_arb.top.asset, "ETH")
        self.assertEqual(self.strategy.triangular_arbitrage_module.ccw_arb.left.asset, "BTC")
        self.assertEqual(self.strategy.triangular_arbitrage_module.ccw_arb.right.asset, "USDT")
