from decimal import Decimal
import unittest.mock
import hummingbot.strategy.amm_arb.start as amm_arb_start
from hummingbot.strategy.amm_arb.amm_arb_config_map import amm_arb_config_map
from hummingbot.strategy.amm_arb.amm_arb import AmmArbStrategy
from test.hummingbot.strategy import assign_config_default


class AMMArbStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy: AmmArbStrategy = None
        self.markets = {"binance": None, "balancer": None}
        self.notifications = []
        self.log_errors = []
        assign_config_default(amm_arb_config_map)
        amm_arb_config_map.get("strategy").value = "amm_arb"
        amm_arb_config_map.get("connector_1").value = "binance"
        amm_arb_config_map.get("market_1").value = "ETH-USDT"
        amm_arb_config_map.get("connector_2").value = "balancer"
        amm_arb_config_map.get("market_2").value = "ETH-USDT"
        amm_arb_config_map.get("order_amount").value = Decimal("1")
        amm_arb_config_map.get("min_profitability").value = Decimal("10")

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

    @unittest.mock.patch('hummingbot.strategy.amm_arb.amm_arb.AmmArbStrategy.add_markets')
    def test_amm_arb_strategy_creation(self, mock):
        amm_arb_start.start(self)
        self.assertEqual(self.strategy._order_amount, Decimal(1))
        self.assertEqual(self.strategy._min_profitability, Decimal("10") / Decimal("100"))
