from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import MagicMock, Mock, PropertyMock, patch

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.event.events import MarketOrderFailureEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.arbitrage_executor.arbitrage_executor import ArbitrageExecutor
from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class TestArbitrageExecutor(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    def setUp(self):
        super().setUp()
        self.strategy = self.create_mock_strategy()
        self.arbitrage_config = MagicMock(spec=ArbitrageExecutorConfig)
        self.arbitrage_config.buying_market = ConnectorPair(connector_name='binance', trading_pair='MATIC-USDT')
        self.arbitrage_config.selling_market = ConnectorPair(connector_name='uniswap_polygon_mainnet', trading_pair='WMATIC-USDT')
        self.arbitrage_config.min_profitability = Decimal('0.01')
        self.arbitrage_config.order_amount = Decimal('1')
        self.arbitrage_config.max_retries = 3
        self.update_interval = 0.5
        self.executor = ArbitrageExecutor(self.strategy, self.arbitrage_config, self.update_interval)
        self.set_loggers(loggers=[self.executor.logger()])

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

    def test_is_arbitrage_valid(self):
        self.assertTrue(self.executor.is_arbitrage_valid('ETH-USDT', 'ETH-USDT'))
        self.assertTrue(self.executor.is_arbitrage_valid('ETH-BUSD', 'ETH-USDT'))
        self.assertTrue(self.executor.is_arbitrage_valid('ETH-USDT', 'WETH-USDT'))
        self.assertFalse(self.executor.is_arbitrage_valid('ETH-USDT', 'BTC-USDT'))

    def test_net_pnl_quote(self):
        self.executor.close_type = CloseType.COMPLETED
        self.executor._buy_order = Mock(spec=TrackedOrder)
        self.executor._sell_order = Mock(spec=TrackedOrder)
        self.executor._buy_order.order.executed_amount_base = Decimal('1')
        self.executor._sell_order.order.executed_amount_base = Decimal('1')
        self.executor._buy_order.average_executed_price = Decimal('100')
        self.executor._sell_order.average_executed_price = Decimal('200')
        self.executor._buy_order.cum_fees_quote = Decimal('1')
        self.executor._sell_order.cum_fees_quote = Decimal('1')
        self.executor._status = RunnableStatus.TERMINATED
        self.assertEqual(self.executor.get_net_pnl_quote(), Decimal('98'))
        self.assertEqual(self.executor.get_net_pnl_pct(), Decimal('98'))

    @patch.object(ArbitrageExecutor, "get_resulting_price_for_amount")
    @patch.object(ArbitrageExecutor, "get_tx_cost_in_asset")
    async def test_control_task_not_started_not_profitable(self, tx_cost_mock, resulting_price_mock):
        tx_cost_mock.return_value = Decimal('0.01')
        resulting_price_mock.side_effect = [Decimal('100'), Decimal('102')]
        self.executor._status = RunnableStatus.RUNNING
        await self.executor.control_task()
        self.assertEqual(self.executor._status, RunnableStatus.RUNNING)

    @patch.object(ArbitrageExecutor, "place_order")
    @patch.object(ArbitrageExecutor, "get_resulting_price_for_amount")
    @patch.object(ArbitrageExecutor, "get_tx_cost_in_asset")
    async def test_control_task_profitable(self, tx_cost_mock, resulting_price_mock, place_order_mock):
        tx_cost_mock.return_value = Decimal('0.01')
        resulting_price_mock.side_effect = [Decimal('100'), Decimal('104')]
        place_order_mock.side_effect = ['OID-BUY', 'OID-SELL']
        self.executor._status = RunnableStatus.RUNNING
        await self.executor.control_task()
        self.assertEqual(self.executor._status, RunnableStatus.SHUTTING_DOWN)
        self.assertEqual(self.executor.buy_order.order_id, 'OID-BUY')
        self.assertEqual(self.executor.sell_order.order_id, 'OID-SELL')

    async def test_control_task_max_retries(self):
        self.executor._status = RunnableStatus.SHUTTING_DOWN
        self.executor._cumulative_failures = 4
        await self.executor.control_task()
        self.assertEqual(self.executor.close_type, CloseType.FAILED)
        self.assertEqual(self.executor._status, RunnableStatus.TERMINATED)

    async def test_control_task_complete(self):
        self.executor._status = RunnableStatus.SHUTTING_DOWN
        self.executor._cumulative_failures = 0
        self.executor._buy_order = Mock(spec=TrackedOrder)
        self.executor._sell_order = Mock(spec=TrackedOrder)
        self.executor._buy_order.order.is_filled = True
        self.executor._sell_order.order.is_filled = True
        await self.executor.control_task()
        self.assertEqual(self.executor.close_type, CloseType.COMPLETED)
        self.assertEqual(self.executor._status, RunnableStatus.TERMINATED)

    def test_to_format_status(self):
        self.executor._status = RunnableStatus.RUNNING
        self.executor._last_buy_price = Decimal('100')
        self.executor._last_sell_price = Decimal('102')
        self.executor._last_tx_cost = Decimal('0.01')
        format_status = "".join(self.executor.to_format_status())
        self.assertIn(f"Arbitrage Status: {RunnableStatus.RUNNING}", format_status)
        self.assertIn("Trade PnL (%): 2.00 % | TX Cost (%): -1.00 % | Net PnL (%): 1.00 %", format_status)

    @patch.object(ArbitrageExecutor, "place_order")
    def test_process_order_failed_event_increments_cumulative_failures(self, _):
        self.executor._cumulative_failures = 0
        self.executor.buy_order.order_id = "123"
        self.executor.sell_order.order_id = "321"
        market = MagicMock()
        buy_order_failed_event = MarketOrderFailureEvent(
            timestamp=123456789,
            order_id=self.executor.buy_order.order_id,
            order_type=OrderType.MARKET,
        )
        self.executor.process_order_failed_event("102", market, buy_order_failed_event)
        self.assertEqual(self.executor._cumulative_failures, 1)

        sell_order_failed_event = MarketOrderFailureEvent(
            timestamp=123456789,
            order_id=self.executor.sell_order.order_id,
            order_type=OrderType.MARKET,
        )
        self.executor.process_order_failed_event("102", market, sell_order_failed_event)
        self.assertEqual(self.executor._cumulative_failures, 2)
