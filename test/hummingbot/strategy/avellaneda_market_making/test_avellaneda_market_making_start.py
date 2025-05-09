import datetime
import logging
import unittest.mock
from decimal import Decimal

import hummingbot.strategy.avellaneda_market_making.start as strategy_start
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.strategy.avellaneda_market_making.avellaneda_market_making_config_map_pydantic import (
    AvellanedaMarketMakingConfigMap,
    FromDateToDateModel,
    MultiOrderLevelModel,
    TrackHangingOrdersModel,
)


class AvellanedaStartTest(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.strategy = None
        self.markets = {"binance": ExchangeBase(client_config_map=ClientConfigAdapter(ClientConfigMap()))}
        self.notifications = []
        self.log_records = []
        self.base = "ETH"
        self.quote = "BTC"
        self.strategy_config_map = ClientConfigAdapter(
            AvellanedaMarketMakingConfigMap(
                exchange="binance",
                market=combine_to_hb_trading_pair(self.base, self.quote),
                execution_timeframe_mode=FromDateToDateModel(
                    start_datetime="2021-11-18 15:00:00",
                    end_datetime="2021-11-18 16:00:00",
                ),
                order_amount=60,
                order_refresh_time=60,
                hanging_orders_mode=TrackHangingOrdersModel(
                    hanging_orders_cancel_pct=1,
                ),
                order_levels_mode=MultiOrderLevelModel(
                    order_levels=4,
                    level_distances=1,
                ),
                min_spread=2,
                risk_factor=1.11,
                order_amount_shape_factor=0.33,
            )
        )

        self.raise_exception_for_market_initialization = False
        self._logger = None

    def _initialize_market_assets(self, market, trading_pairs):
        return [("ETH", "USDT")]

    def _initialize_markets(self, market_names):
        if self.raise_exception_for_market_initialization:
            raise Exception("Exception for testing")

    def notify(self, message):
        self.notifications.append(message)

    def logger(self):
        if self._logger is None:
            self._logger = logging.getLogger(self.__class__.__name__)
            self._logger.addHandler(self)
        return self._logger

    def handle(self, record):
        self.log_records.append(record)

    @unittest.mock.patch('hummingbot.strategy.avellaneda_market_making.start.HummingbotApplication')
    def test_parameters_strategy_creation(self, mock_hbot):
        mock_hbot.main_application().strategy_file_name = "test.yml"
        strategy_start.start(self)
        self.assertEqual(self.strategy.execution_timeframe, "from_date_to_date")
        self.assertEqual(self.strategy.start_time, datetime.datetime(2021, 11, 18, 15, 0))
        self.assertEqual(self.strategy.end_time, datetime.datetime(2021, 11, 18, 16, 0))
        self.assertEqual(self.strategy.min_spread, Decimal("2"))
        self.assertEqual(self.strategy.gamma, Decimal("1.11"))
        self.assertEqual(self.strategy.eta, Decimal("0.33"))
        self.assertEqual(self.strategy.order_levels, Decimal("4"))
        self.assertEqual(self.strategy.level_distances, Decimal("1"))
        self.assertTrue(all(c is not None for c in (self.strategy.gamma, self.strategy.eta)))
        strategy_start.start(self)
        self.assertTrue(all(c is not None for c in (self.strategy.min_spread, self.strategy.gamma)))

    def test_strategy_creation_when_something_fails(self):
        self.raise_exception_for_market_initialization = True
        strategy_start.start(self)
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(self.notifications[0], "Exception for testing")
        self.assertEqual(len(self.log_records), 1)
        self.assertEqual(self.log_records[0].getMessage(), "Unknown error during initialization.")
