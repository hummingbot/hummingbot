from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import MagicMock, PropertyMock, patch

from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, TradeUpdate
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.event.events import BuyOrderCreatedEvent, MarketOrderFailureEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.twap_executor.data_types import TWAPExecutorConfig, TWAPMode
from hummingbot.strategy_v2.executors.twap_executor.twap_executor import TWAPExecutor
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


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
            limit_order_buffer=Decimal("0.1"),
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

    @property
    def in_flight_order_taker(self):
        return InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=self.twap_config_long_taker.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("120"),
            creation_timestamp=1,
            initial_state=OrderState.OPEN
        )

    @patch.object(TWAPExecutor, "get_price", MagicMock(return_value=Decimal("120")))
    async def test_control_task_create_order_taker(self):
        executor = self.get_twap_executor_from_config(self.twap_config_long_taker)
        executor._status = RunnableStatus.RUNNING
        await executor.control_task()
        self.assertEqual(executor._order_plan[1].order_id, "OID-BUY-1")

    @patch.object(TWAPExecutor, "get_price", MagicMock(return_value=Decimal("120")))
    async def test_control_task_create_order_maker(self):
        executor = self.get_twap_executor_from_config(self.twap_config_long_maker)
        executor._status = RunnableStatus.RUNNING
        await executor.control_task()
        self.assertEqual(executor._order_plan[1].order_id, "OID-BUY-1")

    @patch.object(TWAPExecutor, "get_price", MagicMock(return_value=Decimal("120")))
    async def test_control_refresh_order(self):
        executor = self.get_twap_executor_from_config(self.twap_config_long_maker)
        executor._status = RunnableStatus.RUNNING
        await executor.control_task()
        executor._order_plan[1].order = self.in_flight_order_maker
        await executor.control_task()
        self.assertEqual(executor._order_plan[1].order_id, "OID-BUY-3")

    @patch.object(TWAPExecutor, 'get_trading_rules')
    @patch.object(TWAPExecutor, 'adjust_order_candidates')
    def test_validate_sufficient_balance(self, mock_adjust_order_candidates, mock_get_trading_rules):
        # Mock trading rules
        trading_rules = TradingRule(trading_pair="ETH-USDT", min_order_size=Decimal("0.1"),
                                    min_price_increment=Decimal("0.1"), min_base_amount_increment=Decimal("0.1"))
        mock_get_trading_rules.return_value = trading_rules
        executor = TWAPExecutor(self.strategy, self.twap_config_long_taker)
        # Mock order candidate
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
        executor.validate_sufficient_balance()
        self.assertNotEqual(executor.close_type, CloseType.INSUFFICIENT_BALANCE)

        # Test for insufficient balance
        order_candidate.amount = Decimal("0")
        mock_adjust_order_candidates.return_value = [order_candidate]
        executor.validate_sufficient_balance()
        self.assertEqual(executor.close_type, CloseType.INSUFFICIENT_BALANCE)
        self.assertEqual(executor.status, RunnableStatus.TERMINATED)

    async def test_evaluate_all_orders_closed(self):
        executor = self.get_twap_executor_from_config(self.twap_config_long_taker)
        await executor.evaluate_all_orders_closed()
        self.assertEqual(executor.status, RunnableStatus.TERMINATED)

    async def test_early_stop(self):
        executor = self.get_twap_executor_from_config(self.twap_config_long_taker)
        executor._status = RunnableStatus.RUNNING
        executor.early_stop()
        self.assertEqual(executor.status, RunnableStatus.SHUTTING_DOWN)

    @patch.object(TWAPExecutor, "get_in_flight_order")
    def test_process_order_created_event(self, mock_get_in_flight_order):
        mock_get_in_flight_order.return_value = self.in_flight_order_taker
        event = BuyOrderCreatedEvent(
            timestamp=1,
            type=OrderType.MARKET,
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price=Decimal("100"),
            order_id="OID-BUY-1",
            creation_timestamp=1
        )
        executor = self.get_twap_executor_from_config(self.twap_config_long_taker)
        executor._status = RunnableStatus.RUNNING
        executor._order_plan[1] = TrackedOrder("OID-BUY-1")
        executor.process_order_created_event(1, self.strategy.connectors["binance"], event)
        self.assertEqual(executor._order_plan[1].order_id, "OID-BUY-1")
        self.assertEqual(executor._order_plan[1].order, self.in_flight_order_taker)

    def test_process_order_failed_event(self):
        executor = self.get_twap_executor_from_config(self.twap_config_long_taker)
        event = MarketOrderFailureEvent(timestamp=1, order_id="OID-BUY-1", order_type=OrderType.MARKET)
        executor._status = RunnableStatus.RUNNING
        executor._order_plan[1] = TrackedOrder("OID-BUY-1")
        executor.process_order_failed_event(1, self.strategy.connectors["binance"], event)
        self.assertEqual(executor._order_plan[1], None)

    @patch.object(TWAPExecutor, "get_price", MagicMock(return_value=Decimal("144")))
    def test_trade_pnl_pct(self):
        executor = self.get_twap_executor_from_config(self.twap_config_long_taker)
        executor._order_plan[1] = TrackedOrder("OID-BUY-1")
        executor._order_plan[1].order = self.in_flight_order_taker
        executor._order_plan[1].order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-SELL-1",
                exchange_order_id="EOID4",
                trading_pair="ETH-USDT",
                fill_price=Decimal("120"),
                fill_base_amount=Decimal("1"),
                fill_quote_amount=Decimal("120"),
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))]),
                fill_timestamp=10,
            )
        )
        self.assertEqual(executor.trade_pnl_pct, Decimal("0.2"))
