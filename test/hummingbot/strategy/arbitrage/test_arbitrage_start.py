from decimal import Decimal
import unittest.mock
import hummingbot.strategy.arbitrage.start as arbitrage_start
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.strategy.arbitrage.arbitrage_config_map import arbitrage_config_map
from hummingbot.strategy.arbitrage.arbitrage import ArbitrageStrategy
from test.hummingbot.strategy import assign_config_default


class ArbitrageStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy: ArbitrageStrategy = None
        self.markets = {"binance": ConnectorBase(), "balancer": ConnectorBase()}
        self.notifications = []
        self.log_errors = []
        assign_config_default(arbitrage_config_map)
        arbitrage_config_map.get("primary_market").value = "binance"
        arbitrage_config_map.get("secondary_market").value = "balancer"
        arbitrage_config_map.get("primary_market_trading_pair").value = "ETH-USDT"
        arbitrage_config_map.get("secondary_market_trading_pair").value = "ETH-USDT"
        arbitrage_config_map.get("min_profitability").value = Decimal("10")
        arbitrage_config_map.get("use_oracle_conversion_rate").value = False

    def _initialize_market_assets(self, market, trading_pairs):
        return [("ETH", "USDT")]

    def _initialize_markets(self, market_names):
        pass

    def _notify(self, message):
        self.notifications.append(message)

    def logger(self):
        return self

    def error(self, message, exc_info):
        self.log_errors.append(message)

    def test_strategy_creation(self):
        arbitrage_start.start(self)
        self.assertEqual(self.strategy.min_profitability, Decimal("10") / Decimal("100"))
        self.assertEqual(self.strategy.use_oracle_conversion_rate, False)
