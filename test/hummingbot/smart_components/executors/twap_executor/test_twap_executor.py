from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import MagicMock, PropertyMock, patch

from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.smart_components.executors.twap_executor.data_types import TWAPExecutorConfig, TWAPMode
from hummingbot.smart_components.executors.twap_executor.twap_executor import TWAPExecutor
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class TestTWAPExecutor(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    def setUp(self) -> None:
        super().setUp()
        self.strategy = self.create_mock_strategy()
        self.update_interval = 0.5

    @staticmethod
    def create_mock_strategy():
        market = MagicMock()
        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock(spec=ScriptStrategyBase)
        type(strategy).market_info = PropertyMock(return_value=market_info)
        type(strategy).trading_pair = PropertyMock(return_value="ETH-USDT")
        type(strategy).current_timestamp = PropertyMock(side_effect=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        strategy.buy.side_effect = ["OID-BUY-1", "OID-BUY-2", "OID-BUY-3"]
        strategy.sell.side_effect = ["OID-SELL-1", "OID-SELL-2", "OID-SELL-3"]
        strategy.cancel.return_value = None
        connector = MagicMock(spec=ExchangePyBase)
        type(connector).trading_rules = PropertyMock(return_value={"ETH-USDT": TradingRule(trading_pair="ETH-USDT")})
        strategy.connectors = {
            "binance": connector,
        }
        return strategy

    def get_twap_executor_from_config(self, config: TWAPExecutorConfig):
        executor = TWAPExecutor(self.strategy, config, self.update_interval)
        self.set_loggers(loggers=[executor.logger()])
        return executor

    @property
    def twap_config_long_taker(self):
        return TWAPExecutorConfig(
            timestamp=1,
            side=TradeType.BUY,
            trading_pair="ETH-USDT",
            connector_name="binance",
            total_amount_quote=Decimal("100"),
            total_duration=10,
            order_interval=5,
            mode=TWAPMode.TAKER,
        )

    @property
    def twap_config_long_maker(self):
        return TWAPExecutorConfig(
            timestamp=1,
            side=TradeType.BUY,
            trading_pair="ETH-USDT",
            connector_name="binance",
            total_amount_quote=Decimal("100"),
            total_duration=10,
            order_interval=5,
            mode=TWAPMode.MAKER,
            order_resubmission_time=1,
        )

    @property
    def in_flight_order_maker(self):
        return InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=self.twap_config_long_maker.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            amount=Decimal("1"),
            price=Decimal("120"),
            creation_timestamp=1,
            initial_state=OrderState.OPEN
        )

    @patch.object(TWAPExecutor, "get_price", MagicMock(return_value=Decimal("120")))
    async def test_control_task_create_order_taker(self):
        executor = self.get_twap_executor_from_config(self.twap_config_long_taker)
        executor._status = SmartComponentStatus.RUNNING
        await executor.control_task()
        self.assertEqual(executor._order_plan[1].order_id, "OID-BUY-1")

    @patch.object(TWAPExecutor, "get_price", MagicMock(return_value=Decimal("120")))
    async def test_control_task_create_order_maker(self):
        executor = self.get_twap_executor_from_config(self.twap_config_long_maker)
        executor._status = SmartComponentStatus.RUNNING
        await executor.control_task()
        self.assertEqual(executor._order_plan[1].order_id, "OID-BUY-1")

    @patch.object(TWAPExecutor, "get_price", MagicMock(return_value=Decimal("120")))
    async def test_control_refresh_order(self):
        executor = self.get_twap_executor_from_config(self.twap_config_long_maker)
        executor._status = SmartComponentStatus.RUNNING
        await executor.control_task()
        executor._order_plan[1].order = self.in_flight_order_maker
        await executor.control_task()
        self.assertEqual(executor._order_plan[1].order_id, "OID-BUY-3")
