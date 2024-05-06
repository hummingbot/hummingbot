from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import MagicMock, Mock, PropertyMock, patch

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.event.events import MarketOrderFailureEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.arbitrage_executor.arbitrage_executor import ArbitrageExecutor
from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import (
    ArbitrageExecutorConfig,
    ArbitrageExecutorStatus,
)
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.models.executors import TrackedOrder


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
        self.assertFalse(self.executor.is_arbitrage_valid('ETH-USDT', 'ETH-BTC'))

    def test_net_pnl_quote(self):
        self.executor.arbitrage_status = ArbitrageExecutorStatus.COMPLETED
        self.executor._buy_order = Mock(spec=TrackedOrder)
        self.executor._sell_order = Mock(spec=TrackedOrder)
        self.executor._buy_order.order.executed_amount_base = Decimal('1')
        self.executor._sell_order.order.executed_amount_base = Decimal('1')
        self.executor._buy_order.average_executed_price = Decimal('100')
        self.executor._sell_order.average_executed_price = Decimal('200')
        self.executor._buy_order.cum_fees_quote = Decimal('1')
        self.executor._sell_order.cum_fees_quote = Decimal('1')
        self.assertEqual(self.executor.net_pnl_quote, Decimal('98'))
        self.assertEqual(self.executor.net_pnl_pct, Decimal('98'))

    @patch.object(ArbitrageExecutor, 'place_order')
    def test_place_buy_arbitrage_order(self, mock_place_order):
        mock_place_order.return_value = 'order_id'
        self.executor.place_buy_arbitrage_order()
        mock_place_order.assert_called_once_with(
            connector_name=self.arbitrage_config.buying_market.connector_name,
            trading_pair=self.arbitrage_config.buying_market.trading_pair,
            order_type=OrderType.MARKET,
            side=TradeType.BUY,
            amount=self.arbitrage_config.order_amount,
            price=self.executor._last_buy_price,
        )

    @patch.object(ArbitrageExecutor, 'place_order')
    def test_place_sell_arbitrage_order(self, mock_place_order):
        mock_place_order.return_value = 'order_id'
        self.executor.place_sell_arbitrage_order()
        mock_place_order.assert_called_once_with(
            connector_name=self.arbitrage_config.selling_market.connector_name,
            trading_pair=self.arbitrage_config.selling_market.trading_pair,
            order_type=OrderType.MARKET,
            side=TradeType.SELL,
            amount=self.arbitrage_config.order_amount,
            price=self.executor._last_sell_price,
        )

    @patch.object(ArbitrageExecutor, "get_resulting_price_for_amount")
    @patch.object(ArbitrageExecutor, "get_tx_cost_in_asset")
    async def test_control_task_not_started_not_profitable(self, tx_cost_mock, resulting_price_mock):
        tx_cost_mock.return_value = Decimal('0.01')
        resulting_price_mock.side_effect = [Decimal('100'), Decimal('102')]
        self.executor.arbitrage_status = ArbitrageExecutorStatus.NOT_STARTED
        await self.executor.control_task()
        self.assertEqual(self.executor.arbitrage_status, ArbitrageExecutorStatus.NOT_STARTED)

    @patch.object(ArbitrageExecutor, "place_order")
    @patch.object(ArbitrageExecutor, "get_resulting_price_for_amount")
    @patch.object(ArbitrageExecutor, "get_tx_cost_in_asset")
    async def test_control_task_not_started_profitable(self, tx_cost_mock, resulting_price_mock, place_order_mock):
        tx_cost_mock.return_value = Decimal('0.01')
        resulting_price_mock.side_effect = [Decimal('100'), Decimal('104')]
        place_order_mock.side_effect = ['OID-BUY', 'OID-SELL']
        self.executor.arbitrage_status = ArbitrageExecutorStatus.NOT_STARTED
        await self.executor.control_task()
        self.assertEqual(self.executor.arbitrage_status, ArbitrageExecutorStatus.ACTIVE_ARBITRAGE)
        self.assertEqual(self.executor.buy_order.order_id, 'OID-BUY')
        self.assertEqual(self.executor.sell_order.order_id, 'OID-SELL')

    async def test_control_task_active_arbitrage_max_retries(self):
        self.executor.arbitrage_status = ArbitrageExecutorStatus.ACTIVE_ARBITRAGE
        self.executor._cumulative_failures = 4
        await self.executor.control_task()
        self.assertEqual(self.executor.arbitrage_status, ArbitrageExecutorStatus.FAILED)

    async def test_control_task_active_arbitrage_complete(self):
        self.executor.arbitrage_status = ArbitrageExecutorStatus.ACTIVE_ARBITRAGE
        self.executor._cumulative_failures = 0
        self.executor._buy_order = Mock(spec=TrackedOrder)
        self.executor._sell_order = Mock(spec=TrackedOrder)
        self.executor._buy_order.order.is_done.return_value = True
        self.executor._sell_order.order.is_done.return_value = True
        await self.executor.control_task()
        self.assertEqual(self.executor.arbitrage_status, ArbitrageExecutorStatus.COMPLETED)

    @patch.object(ArbitrageExecutor, "get_trade_pnl_pct")
    async def test_price_not_available_logs_exception(self, trade_pnl_pct_mock):
        trade_pnl_pct_mock.side_effect = Exception("Price not available")
        self.executor.arbitrage_status = ArbitrageExecutorStatus.NOT_STARTED
        self.executor._cumulative_failures = 0
        try:
            await self.executor.control_task()
        except Exception:
            pass
        self.is_logged("ERROR", "Error calculating profitability: Price not available")

    def test_to_format_status_not_started(self):
        self.executor.arbitrage_status = ArbitrageExecutorStatus.NOT_STARTED
        format_status = "".join(self.executor.to_format_status())
        self.assertIn("Arbitrage Status: ArbitrageExecutorStatus.NOT_STARTED", format_status)
        self.assertIn("Trade PnL (%): 0.00 % | TX Cost (%): -100.00 % | Net PnL (%): -100.00 %", format_status)

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
