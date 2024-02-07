from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import MagicMock, PropertyMock, patch

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import TradeType
from hummingbot.smart_components.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.smart_components.executors.dca_executor.dca_executor import DCAExecutor
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class TestDCAExecutor(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
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
        strategy.buy.side_effect = ["OID-BUY-1", "OID-BUY-2", "OID-BUY-3"]
        strategy.sell.side_effect = ["OID-SELL-1", "OID-SELL-2", "OID-SELL-3"]
        strategy.cancel.return_value = None
        strategy.connectors = {
            "binance": MagicMock(spec=ConnectorBase),
        }
        return strategy

    def get_dca_executor_from_config(self, config: DCAExecutorConfig):
        executor = DCAExecutor(self.strategy, config, self.update_interval)
        self.set_loggers(loggers=[executor.logger()])
        return executor

    @patch.object(DCAExecutor, "get_price", MagicMock(return_value=Decimal("120")))
    async def test_control_task_open_orders(self):
        config = DCAExecutorConfig(id="test", timestamp=123, side=TradeType.BUY, exchange="binance",
                                   trading_pair="ETH-USDT",
                                   amounts_quote=[Decimal(10), Decimal(20), Decimal(30)],
                                   prices=[Decimal(100), Decimal(80), Decimal(60)])
        executor = self.get_dca_executor_from_config(config)
        executor._status = SmartComponentStatus.RUNNING
        await executor.control_task()
        self.assertEqual(executor.active_open_orders[0].order_id, "OID-BUY-1")
        await executor.control_task()
        self.assertEqual(executor.active_open_orders[1].order_id, "OID-BUY-2")
        await executor.control_task()
        self.assertEqual(executor.active_open_orders[2].order_id, "OID-BUY-3")
        self.assertEqual(executor.net_pnl_pct, 0)
        self.assertEqual(executor.net_pnl_quote, 0)
        self.assertEqual(executor.cum_fees_quote, 0)
        self.assertEqual(executor.min_price, Decimal("60"))
        self.assertEqual(executor.max_price, Decimal("100"))
        self.assertEqual(executor.max_amount_quote, Decimal("60"))
        self.assertEqual(executor.close_filled_amount_quote, Decimal("0"))
