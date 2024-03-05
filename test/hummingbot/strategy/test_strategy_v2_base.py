from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock, patch

import pandas as pd

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange
from hummingbot.core.clock import Clock
from hummingbot.core.clock_mode import ClockMode
from hummingbot.core.data_type.common import PositionMode, TradeType
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.smart_components.models.executors_info import ExecutorInfo
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase


class TestStrategyV2Base(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        self.start: pd.Timestamp = pd.Timestamp("2021-01-01", tz="UTC")
        self.end: pd.Timestamp = pd.Timestamp("2021-01-01 01:00:00", tz="UTC")
        self.start_timestamp: float = self.start.timestamp()
        self.end_timestamp: float = self.end.timestamp()
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.connector: MockPaperExchange = MockPaperExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap())
        )
        self.connector_name: str = "mock_paper_exchange"
        self.trading_pair: str = "HBOT-USDT"
        self.strategy_config = StrategyV2ConfigBase(markets={self.connector_name: {self.trading_pair}},
                                                    candles_config=[])
        with patch('asyncio.create_task', return_value=MagicMock()):
            self.strategy = StrategyV2Base({self.connector_name: self.connector}, config=self.strategy_config)
        self.strategy.logger().setLevel(1)

    async def test_start(self):
        self.assertFalse(self.strategy.ready_to_trade)
        self.strategy.start(Clock(ClockMode.BACKTEST), self.start_timestamp)
        self.strategy.tick(self.start_timestamp + 10)
        self.assertTrue(self.strategy.ready_to_trade)

    def test_init_markets(self):
        StrategyV2Base.init_markets(self.strategy_config)
        self.assertIn(self.connector_name, StrategyV2Base.markets)
        self.assertIn(self.trading_pair, StrategyV2Base.markets[self.connector_name])

    def test_store_actions_proposal(self):
        # Setup test executors with all required fields
        executor_1 = ExecutorInfo(
            id="1",
            controller_id="controller_1",
            type="position_executor",
            status=SmartComponentStatus.TERMINATED,
            timestamp=10,
            config=PositionExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT",
                                          connector_name="binance",
                                          side=TradeType.BUY, entry_price=Decimal("100"), amount=Decimal("1")),
            net_pnl_pct=Decimal(0),
            net_pnl_quote=Decimal(0),
            cum_fees_quote=Decimal(0),
            filled_amount_quote=Decimal(0),
            is_active=False,
            is_trading=False,
            custom_info={}
        )
        executor_2 = ExecutorInfo(
            id="2",
            controller_id="controller_2",
            type="position_executor",
            status=SmartComponentStatus.RUNNING,
            timestamp=20,
            config=PositionExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT",
                                          connector_name="binance",
                                          side=TradeType.BUY, entry_price=Decimal("100"), amount=Decimal("1")),
            net_pnl_pct=Decimal(0),
            net_pnl_quote=Decimal(0),
            cum_fees_quote=Decimal(0),
            filled_amount_quote=Decimal(0),
            is_active=True,
            is_trading=True,
            custom_info={}
        )
        self.strategy.executors_info = {"controller_1": [executor_1], "controller_2": [executor_2]}
        self.strategy.closed_executors_buffer = 0

        actions = self.strategy.store_actions_proposal()
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].executor_id, "1")

    def test_get_executors_by_controller(self):
        self.strategy.executors_info = {
            "controller_1": [MagicMock(), MagicMock()],
            "controller_2": [MagicMock()]
        }

        executors = self.strategy.get_executors_by_controller("controller_1")
        self.assertEqual(len(executors), 2)

    def test_get_all_executors(self):
        self.strategy.executors_info = {
            "controller_1": [MagicMock(), MagicMock()],
            "controller_2": [MagicMock()]
        }

        executors = self.strategy.get_all_executors()
        self.assertEqual(len(executors), 3)

    def test_set_leverage(self):
        mock_connector = MagicMock()
        self.strategy.connectors = {"mock": mock_connector}
        self.strategy.set_leverage("mock", "HBOT-USDT", 2)
        mock_connector.set_leverage.assert_called_with("HBOT-USDT", 2)

    def test_set_position_mode(self):
        mock_connector = MagicMock()
        self.strategy.connectors = {"mock": mock_connector}
        self.strategy.set_position_mode("mock", PositionMode.HEDGE)
        mock_connector.set_position_mode.assert_called_with(PositionMode.HEDGE)

    def test_filter_executors(self):
        executors = [MagicMock(status=SmartComponentStatus.RUNNING), MagicMock(status=SmartComponentStatus.TERMINATED)]
        filtered = StrategyV2Base.filter_executors(executors, lambda x: x.status == SmartComponentStatus.RUNNING)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].status, SmartComponentStatus.RUNNING)
