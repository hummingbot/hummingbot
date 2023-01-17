import unittest
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock

from hummingbot.core.data_type.common import OrderType, PositionSide
from hummingbot.strategy.smart_components.position_executor.data_types import (
    PositionConfig,
    PositionExecutorStatus,
    TrackedOrder,
)
from hummingbot.strategy.smart_components.position_executor.position_executor import PositionExecutor


class TestPositionExecutor(unittest.TestCase):
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage().startswith(message)
                   for record in self.log_records)

    def create_mock_strategy(self):
        market = MagicMock()
        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock()
        type(strategy).market_info = PropertyMock(return_value=market_info)
        type(strategy).trading_pair = PropertyMock(return_value="ETH-USDT")

        return strategy

    def get_position_config_market_long(self):
        return PositionConfig(timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                              order_type=OrderType.MARKET,
                              side=PositionSide.LONG, entry_price=Decimal("100"), amount=Decimal("1"),
                              stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60)

    def get_position_config_market_short(self):
        return PositionConfig(timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                              order_type=OrderType.MARKET,
                              side=PositionSide.SHORT, entry_price=Decimal("100"), amount=Decimal("1"),
                              stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60)

    def test_init(self):
        position_config = PositionConfig(timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                                         order_type=OrderType.MARKET,
                                         side=PositionSide.LONG, entry_price=Decimal("100"), amount=Decimal("1"),
                                         stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60)
        strategy = self.create_mock_strategy()
        position_executor = PositionExecutor(position_config, strategy)
        self.assertIsInstance(position_executor._position_config, PositionConfig)
        self.assertEqual(position_executor._position_config, position_config)
        self.assertEqual(position_executor._strategy, strategy)
        self.assertEqual(position_executor._status, PositionExecutorStatus.NOT_STARTED)
        self.assertIsInstance(position_executor._open_order, TrackedOrder)
        self.assertIsInstance(position_executor._take_profit_order, TrackedOrder)
        self.assertIsInstance(position_executor._time_limit_order, TrackedOrder)
        self.assertIsInstance(position_executor._stop_loss_order, TrackedOrder)
        self.assertIsNone(position_executor._close_timestamp)

    def test_status(self):
        position_config = self.get_position_config_market_short()
        strategy = self.create_mock_strategy()
        position_executor = PositionExecutor(position_config, strategy)
        assert position_executor.status == PositionExecutorStatus.NOT_STARTED
        position_executor.status = PositionExecutorStatus.ORDER_PLACED
        assert position_executor.status == PositionExecutorStatus.ORDER_PLACED

    def test_is_closed(self):
        position_config = self.get_position_config_market_short()
        strategy = self.create_mock_strategy()
        position_executor = PositionExecutor(position_config, strategy)
        position_executor.status = PositionExecutorStatus.CLOSED_BY_TIME_LIMIT
        self.assertTrue(position_executor.is_closed)

    def test_control_open_order(self):
        pass
