from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import MagicMock, Mock, PropertyMock, patch

from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import BuyOrderCompletedEvent, BuyOrderCreatedEvent, MarketOrderFailureEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.xemm_executor.data_types import XEMMExecutorConfig
from hummingbot.strategy_v2.executors.xemm_executor.xemm_executor import XEMMExecutor
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class TestXEMMExecutor(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    def setUp(self):
        super().setUp()
        self.strategy = self.create_mock_strategy()
        self.xemm_base_config = self.base_config_long
        self.update_interval = 0.5
        self.executor = XEMMExecutor(self.strategy, self.xemm_base_config, self.update_interval)
        self.set_loggers(loggers=[self.executor.logger()])

    @property
    def base_config_long(self) -> XEMMExecutorConfig:
        return XEMMExecutorConfig(
            timestamp=1234,
            buying_market=ConnectorPair(connector_name='binance', trading_pair='ETH-USDT'),
            selling_market=ConnectorPair(connector_name='kucoin', trading_pair='ETH-USDT'),
            maker_side=TradeType.BUY,
            order_amount=Decimal('100'),
            min_profitability=Decimal('0.01'),
            target_profitability=Decimal('0.015'),
            max_profitability=Decimal('0.02'),
        )

    @property
    def base_config_short(self) -> XEMMExecutorConfig:
        return XEMMExecutorConfig(
            timestamp=1234,
            buying_market=ConnectorPair(connector_name='binance', trading_pair='ETH-USDT'),
            selling_market=ConnectorPair(connector_name='kucoin', trading_pair='ETH-USDT'),
            maker_side=TradeType.BUY,
            order_amount=Decimal('100'),
            min_profitability=Decimal('0.01'),
            target_profitability=Decimal('0.015'),
            max_profitability=Decimal('0.02'),
        )

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
        binance_connector = MagicMock(spec=ExchangePyBase)
        binance_connector.supported_order_types = MagicMock(return_value=[OrderType.LIMIT, OrderType.MARKET])
        kucoin_connector = MagicMock(spec=ExchangePyBase)
        kucoin_connector.supported_order_types = MagicMock(return_value=[OrderType.LIMIT, OrderType.MARKET])
        strategy.connectors = {
            "binance": binance_connector,
            "kucoin": kucoin_connector,
        }
        return strategy

    def test_is_arbitrage_valid(self):
        self.assertTrue(self.executor.is_arbitrage_valid('ETH-USDT', 'ETH-USDT'))
        self.assertTrue(self.executor.is_arbitrage_valid('ETH-BUSD', 'ETH-USDT'))
        self.assertTrue(self.executor.is_arbitrage_valid('ETH-USDT', 'WETH-USDT'))
        self.assertFalse(self.executor.is_arbitrage_valid('ETH-USDT', 'BTC-USDT'))
        self.assertFalse(self.executor.is_arbitrage_valid('ETH-USDT', 'ETH-BTC'))

    def test_net_pnl_long(self):
        self.executor._status = RunnableStatus.TERMINATED
        self.executor.maker_order = Mock(spec=TrackedOrder)
        self.executor.taker_order = Mock(spec=TrackedOrder)
        self.executor.maker_order.executed_amount_base = Decimal('1')
        self.executor.taker_order.executed_amount_base = Decimal('1')
        self.executor.maker_order.average_executed_price = Decimal('100')
        self.executor.taker_order.average_executed_price = Decimal('200')
        self.executor.maker_order.cum_fees_quote = Decimal('1')
        self.executor.taker_order.cum_fees_quote = Decimal('1')
        self.assertEqual(self.executor.net_pnl_quote, Decimal('98'))
        self.assertEqual(self.executor.net_pnl_pct, Decimal('0.98'))

    def test_net_pnl_short(self):
        self.executor._status = RunnableStatus.TERMINATED
        self.executor.config = self.base_config_short
        self.executor.maker_order = Mock(spec=TrackedOrder)
        self.executor.taker_order = Mock(spec=TrackedOrder)
        self.executor.maker_order.executed_amount_base = Decimal('1')
        self.executor.taker_order.executed_amount_base = Decimal('1')
        self.executor.maker_order.average_executed_price = Decimal('100')
        self.executor.taker_order.average_executed_price = Decimal('200')
        self.executor.maker_order.cum_fees_quote = Decimal('1')
        self.executor.taker_order.cum_fees_quote = Decimal('1')
        self.assertEqual(self.executor.net_pnl_quote, Decimal('98'))
        self.assertEqual(self.executor.net_pnl_pct, Decimal('0.98'))

    @patch.object(XEMMExecutor, 'get_trading_rules')
    @patch.object(XEMMExecutor, 'adjust_order_candidates')
    def test_validate_sufficient_balance(self, mock_adjust_order_candidates, mock_get_trading_rules):
        # Mock trading rules
        trading_rules = TradingRule(trading_pair="ETH-USDT", min_order_size=Decimal("0.1"),
                                    min_price_increment=Decimal("0.1"), min_base_amount_increment=Decimal("0.1"))
        mock_get_trading_rules.return_value = trading_rules
        order_candidate = OrderCandidate(
            trading_pair="ETH-USDT",
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100")
        )
        # Test for sufficient balance
        mock_adjust_order_candidates.return_value = [order_candidate]
        self.executor.validate_sufficient_balance()
        self.assertNotEqual(self.executor.close_type, CloseType.INSUFFICIENT_BALANCE)

        # Test for insufficient balance
        order_candidate.amount = Decimal("0")
        mock_adjust_order_candidates.return_value = [order_candidate]
        self.executor.validate_sufficient_balance()
        self.assertEqual(self.executor.close_type, CloseType.INSUFFICIENT_BALANCE)
        self.assertEqual(self.executor.status, RunnableStatus.TERMINATED)

    @patch.object(XEMMExecutor, "get_resulting_price_for_amount")
    @patch.object(XEMMExecutor, "get_tx_cost_in_asset")
    async def test_control_task_running_order_not_placed(self, tx_cost_mock, resulting_price_mock):
        tx_cost_mock.return_value = Decimal('0.01')
        resulting_price_mock.return_value = Decimal("100")
        self.executor._status = RunnableStatus.RUNNING
        await self.executor.control_task()
        self.assertEqual(self.executor._status, RunnableStatus.RUNNING)
        self.assertEqual(self.executor.maker_order.order_id, "OID-BUY-1")
        self.assertEqual(self.executor._maker_target_price, Decimal("98.48"))

    @patch.object(XEMMExecutor, "get_resulting_price_for_amount")
    @patch.object(XEMMExecutor, "get_tx_cost_in_asset")
    async def test_control_task_running_order_placed_refresh_condition_min_profitability(self, tx_cost_mock,
                                                                                         resulting_price_mock):
        tx_cost_mock.return_value = Decimal('0.01')
        resulting_price_mock.return_value = Decimal("100")
        self.executor._status = RunnableStatus.RUNNING
        self.executor.maker_order = Mock(spec=TrackedOrder)
        self.executor.maker_order.order_id = "OID-BUY-1"
        self.executor.maker_order.order = InFlightOrder(
            creation_timestamp=1234,
            trading_pair="ETH-USDT",
            client_order_id="OID-BUY-1",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("100"),
            price=Decimal("99.5"),
            initial_state=OrderState.OPEN,
        )
        await self.executor.control_task()
        self.assertEqual(self.executor._status, RunnableStatus.RUNNING)
        self.assertEqual(self.executor.maker_order, None)

    @patch.object(XEMMExecutor, "get_resulting_price_for_amount")
    @patch.object(XEMMExecutor, "get_tx_cost_in_asset")
    async def test_control_task_running_order_placed_refresh_condition_max_profitability(self, tx_cost_mock,
                                                                                         resulting_price_mock):
        tx_cost_mock.return_value = Decimal('0.01')
        resulting_price_mock.return_value = Decimal("103")
        self.executor._status = RunnableStatus.RUNNING
        self.executor.maker_order = Mock(spec=TrackedOrder)
        self.executor.maker_order.order_id = "OID-BUY-1"
        self.executor.maker_order.order = InFlightOrder(
            creation_timestamp=1234,
            trading_pair="ETH-USDT",
            client_order_id="OID-BUY-1",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("100"),
            price=Decimal("99.5"),
            initial_state=OrderState.OPEN,
        )
        await self.executor.control_task()
        self.assertEqual(self.executor._status, RunnableStatus.RUNNING)
        self.assertEqual(self.executor.maker_order, None)

    async def test_control_task_shut_down_process(self):
        self.executor.maker_order = Mock(spec=TrackedOrder)
        self.executor.maker_order.is_done = True
        self.executor.taker_order = Mock(spec=TrackedOrder)
        self.executor.taker_order.is_done = True
        self.executor._status = RunnableStatus.SHUTTING_DOWN
        await self.executor.control_task()
        self.assertEqual(self.executor._status, RunnableStatus.TERMINATED)

    @patch.object(XEMMExecutor, "get_in_flight_order")
    def test_process_order_created_event(self, in_flight_order_mock):
        self.executor._status = RunnableStatus.RUNNING
        in_flight_order_mock.side_effect = [
            InFlightOrder(
                client_order_id="OID-BUY-1",
                creation_timestamp=1234,
                trading_pair="ETH-USDT",
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                amount=Decimal("100"),
                price=Decimal("100"),
            ),
            InFlightOrder(
                client_order_id="OID-SELL-1",
                creation_timestamp=1234,
                trading_pair="ETH-USDT",
                order_type=OrderType.MARKET,
                trade_type=TradeType.SELL,
                amount=Decimal("100"),
                price=Decimal("100"),
            )
        ]

        self.executor.maker_order = TrackedOrder(order_id="OID-BUY-1")
        self.executor.taker_order = TrackedOrder(order_id="OID-SELL-1")
        buy_order_created_event = BuyOrderCreatedEvent(
            timestamp=1234,
            type=OrderType.LIMIT,
            creation_timestamp=1233,
            order_id="OID-BUY-1",
            trading_pair="ETH-USDT",
            amount=Decimal("100"),
            price=Decimal("100"),
        )
        sell_order_created_event = BuyOrderCreatedEvent(
            timestamp=1234,
            type=OrderType.MARKET,
            creation_timestamp=1233,
            order_id="OID-SELL-1",
            trading_pair="ETH-USDT",
            amount=Decimal("100"),
            price=Decimal("100"),
        )
        self.assertEqual(self.executor.maker_order.order, None)
        self.assertEqual(self.executor.taker_order.order, None)
        self.executor.process_order_created_event(1, MagicMock(), buy_order_created_event)
        self.assertEqual(self.executor.maker_order.order.client_order_id, "OID-BUY-1")
        self.executor.process_order_created_event(1, MagicMock(), sell_order_created_event)
        self.assertEqual(self.executor.taker_order.order.client_order_id, "OID-SELL-1")

    def test_process_order_completed_event(self):
        self.executor._status = RunnableStatus.RUNNING
        self.executor.maker_order = TrackedOrder(order_id="OID-BUY-1")
        self.assertEqual(self.executor.taker_order, None)
        buy_order_created_event = BuyOrderCompletedEvent(
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=Decimal("100"),
            quote_asset_amount=Decimal("100"),
            order_type=OrderType.LIMIT,
            timestamp=1234,
            order_id="OID-BUY-1",
        )
        self.executor.process_order_completed_event(1, MagicMock(), buy_order_created_event)
        self.assertEqual(self.executor.status, RunnableStatus.SHUTTING_DOWN)
        self.assertEqual(self.executor.taker_order.order_id, "OID-SELL-1")

    def test_process_order_failed_event(self):
        self.executor.maker_order = TrackedOrder(order_id="OID-BUY-1")
        maker_failure_event = MarketOrderFailureEvent(
            timestamp=1234,
            order_id="OID-BUY-1",
            order_type=OrderType.LIMIT,
        )
        self.executor.process_order_failed_event(1, MagicMock(), maker_failure_event)
        self.assertEqual(self.executor.maker_order, None)

        self.executor.taker_order = TrackedOrder(order_id="OID-SELL-0")
        taker_failure_event = MarketOrderFailureEvent(
            timestamp=1234,
            order_id="OID-SELL-0",
            order_type=OrderType.MARKET,
        )
        self.executor.process_order_failed_event(1, MagicMock(), taker_failure_event)
        self.assertEqual(self.executor.taker_order.order_id, "OID-SELL-1")

    def test_get_custom_info(self):
        self.assertEqual(self.executor.get_custom_info(), {'maker_connector': 'binance',
                                                           'maker_trading_pair': 'ETH-USDT',
                                                           'max_profitability': Decimal('0.02'),
                                                           'min_profitability': Decimal('0.01'),
                                                           'side': TradeType.BUY,
                                                           'taker_connector': 'kucoin',
                                                           'taker_trading_pair': 'ETH-USDT',
                                                           'target_profitability_pct': Decimal('0.015'),
                                                           'trade_profitability': Decimal('0'),
                                                           'tx_cost': Decimal('1'),
                                                           'tx_cost_pct': Decimal('1')})

        def test_to_format_status(self):
            self.assertIn("Maker Side: TradeType.BUY", self.executor.to_format_status())
