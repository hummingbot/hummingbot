import unittest.mock
from decimal import Decimal
from test.hummingbot.strategy import assign_config_default

import hummingbot.strategy.uniswap_v3_lp.start as uniswap_v3_lp_start
from hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp import UniswapV3LpStrategy
from hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp_config_map import uniswap_v3_lp_config_map


class UniswapV3LpStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy: UniswapV3LpStrategy = None
        self.markets = {"uniswapLP": None}
        self.notifications = []
        self.log_errors = []
        assign_config_default(uniswap_v3_lp_config_map)
        uniswap_v3_lp_config_map.get("strategy").value = "uniswap_v3_lp"
        uniswap_v3_lp_config_map.get("connector").value = "uniswapLP"
        uniswap_v3_lp_config_map.get("market").value = "ETH-USDT"
        uniswap_v3_lp_config_map.get("fee_tier").value = "LOW"
        uniswap_v3_lp_config_map.get("price_spread").value = Decimal("1")
        uniswap_v3_lp_config_map.get("amount").value = Decimal("1")
        uniswap_v3_lp_config_map.get("min_profitability").value = Decimal("10")

    def _initialize_market_assets(self, market, trading_pairs):
        pass

    def _initialize_markets(self, market_names):
        pass

    def _notify(self, message):
        self.notifications.append(message)

    def logger(self):
        return self

    def error(self, message, exc_info):
        self.log_errors.append(message)

    @unittest.mock.patch('hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp.UniswapV3LpStrategy.add_markets')
    def test_uniswap_v3_lp_strategy_creation(self, mock):
        uniswap_v3_lp_start.start(self)
        self.assertEqual(self.strategy._amount, Decimal(1))
        self.assertEqual(self.strategy._min_profitability, Decimal("10"))
