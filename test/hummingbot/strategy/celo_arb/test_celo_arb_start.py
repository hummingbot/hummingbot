from decimal import Decimal
import unittest.mock
import hummingbot.strategy.celo_arb.start as strategy_start
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.celo_arb.celo_arb_config_map import celo_arb_config_map as strategy_cmap
from test.hummingbot.strategy import assign_config_default


class CeloArbStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy = None
        self.markets = {"binance": ExchangeBase()}
        self.notifications = []
        self.log_errors = []
        assign_config_default(strategy_cmap)
        strategy_cmap.get("secondary_exchange").value = "binance"
        strategy_cmap.get("secondary_market").value = "CELO-USDT"
        strategy_cmap.get("order_amount").value = Decimal("1")
        strategy_cmap.get("min_profitability").value = Decimal("2")
        strategy_cmap.get("celo_slippage_buffer").value = Decimal("3")

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
        strategy_start.start(self)
        self.assertEqual(self.strategy.order_amount, Decimal("1"))
        self.assertEqual(self.strategy.min_profitability, Decimal("0.02"))
        self.assertEqual(self.strategy.celo_slippage_buffer, Decimal("0.03"))
