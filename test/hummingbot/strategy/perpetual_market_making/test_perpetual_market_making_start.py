from decimal import Decimal
import unittest.mock
import hummingbot.strategy.perpetual_market_making.start as strategy_start
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.perpetual_market_making.perpetual_market_making_config_map import (
    perpetual_market_making_config_map as c_map
)
from test.hummingbot.strategy import assign_config_default


class PerpetualMarketMakingStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy = None
        self.markets = {"binance": ExchangeBase()}
        self.notifications = []
        self.log_errors = []
        assign_config_default(c_map)
        c_map.get("derivative").value = "binance"
        c_map.get("market").value = "ETH-USDT"

        c_map.get("leverage").value = Decimal("5")
        c_map.get("order_amount").value = Decimal("1")
        c_map.get("order_refresh_time").value = 60.
        c_map.get("bid_spread").value = Decimal("1")
        c_map.get("ask_spread").value = Decimal("2")

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
        self.assertEqual(self.strategy.order_refresh_time, 60.)
        self.assertEqual(self.strategy.bid_spread, Decimal("0.01"))
        self.assertEqual(self.strategy.ask_spread, Decimal("0.02"))
