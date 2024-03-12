import unittest.mock
from decimal import Decimal
from test.hummingbot.strategy import assign_config_default

import hummingbot.strategy.amm_v3_lp.start as amm_v3_lp_start
from hummingbot.strategy.amm_v3_lp.amm_v3_lp import AmmV3LpStrategy
from hummingbot.strategy.amm_v3_lp.amm_v3_lp_config_map import amm_v3_lp_config_map


class AmmV3LpStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy: AmmV3LpStrategy = None
        self.markets = {"uniswapLP": None}
        self.notifications = []
        self.log_errors = []
        assign_config_default(amm_v3_lp_config_map)
        amm_v3_lp_config_map.get("strategy").value = "amm_v3_lp"
        amm_v3_lp_config_map.get("connector").value = "uniswapLP"
        amm_v3_lp_config_map.get("market").value = "ETH-USDT"
        amm_v3_lp_config_map.get("fee_tier").value = "LOW"
        amm_v3_lp_config_map.get("price_spread").value = Decimal("1")
        amm_v3_lp_config_map.get("amount").value = Decimal("1")
        amm_v3_lp_config_map.get("min_profitability").value = Decimal("10")

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

    @unittest.mock.patch('hummingbot.strategy.amm_v3_lp.amm_v3_lp.AmmV3LpStrategy.add_markets')
    def test_amm_v3_lp_strategy_creation(self, mock):
        amm_v3_lp_start.start(self)
        self.assertEqual(self.strategy._amount, Decimal(1))
        self.assertEqual(self.strategy._min_profitability, Decimal("10"))
