from decimal import Decimal
from functools import partial
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock, PropertyMock, patch

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, TradeUpdate
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy_v2.executors.progressive_executor.data_types import (
    LadderedTrailingStop,
    ProgressiveExecutorConfig,
    YieldTripleBarrierConfig,
)
from hummingbot.strategy_v2.executors.progressive_executor.progressive_executor import ProgressiveExecutor
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class TestProgressiveExecutor(IsolatedAsyncioWrapperTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.strategy = self.create_mock_strategy

        # Mock connector with trading rules
        self.connector = MagicMock()
        self.connector.trading_rules = {
            "ETH-USDT": TradingRule(
                trading_pair="ETH-USDT",
                min_order_size=Decimal("0.1"),
                min_price_increment=Decimal("0.01"),
                min_base_amount_increment=Decimal("0.01"),
            )
        }

        self.strategy.connectors = {"binance": self.connector}

    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def asyncTearDown(self):
        await super().asyncTearDown()

    @property
    def create_mock_strategy(self):
        market = MagicMock()
        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock(spec=StrategyV2Base)
        strategy.market_info = market_info
        strategy.trading_pair = "ETH-USDT"
        strategy.current_timestamp = 1234567890
        strategy.buy.side_effect = ["OID-BUY-1", "OID-BUY-2", "OID-BUY-3"]
        strategy.sell.side_effect = ["OID-SELL-1", "OID-SELL-2", "OID-SELL-3"]
        strategy.cancel.return_value = None
        strategy.connectors = {
            "binance": MagicMock(spec=ConnectorBase),
        }
        return strategy

    def _create_filled_order(self, amount: Decimal, price: Decimal) -> TrackedOrder:
        order = TrackedOrder(order_id="test_id")
        in_flight_order = InFlightOrder(
            client_order_id="test_id",
            trading_pair="ETH-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=amount,
            creation_timestamp=1234567890,
            price=price,
            initial_state=OrderState.FILLED,
        )
        in_flight_order.executed_amount_base = amount
        in_flight_order.executed_amount_quote = amount * price
        order.order = in_flight_order
        return order

    @staticmethod
    def get_basic_config() -> ProgressiveExecutorConfig:
        return ProgressiveExecutorConfig(
            timestamp=1234567890,
            connector_name="binance",
            trading_pair="ETH-USDT",
            side=TradeType.SELL,
            entry_price=Decimal("100"),
            amount=Decimal("1"),
            triple_barrier_config=YieldTripleBarrierConfig(
                apr_yield=Decimal("0.5"),
                stop_loss=Decimal("0.01"),
                take_profit=Decimal("0.02"),
                time_limit=60,
                trailing_stop=LadderedTrailingStop(
                    activation_pnl_pct=Decimal("0.015"),
                    trailing_pct=Decimal("0.005"),
                    take_profit_table=((Decimal("0.05"), Decimal("1")),),
                ),
            ),
        )

    @staticmethod
    def get_progressive_config_market_long():
        return ProgressiveExecutorConfig(
            id="test",
            timestamp=1234567890,
            trading_pair="ETH-USDT",
            connector_name="binance",
            side=TradeType.BUY,
            entry_price=Decimal("100"),
            amount=Decimal("1"),
            triple_barrier_config=YieldTripleBarrierConfig(
                stop_loss=Decimal("0.05"),
                apr_yield=Decimal("3.65"),
                time_limit=60,
                stop_loss_order_type=OrderType.MARKET,
            ),
        )

    @staticmethod
    def get_progressive_config_market_long_tp_market():
        return ProgressiveExecutorConfig(
            id="test-1",
            timestamp=1234567890,
            trading_pair="ETH-USDT",
            connector_name="binance",
            side=TradeType.BUY,
            entry_price=Decimal("100"),
            amount=Decimal("1"),
            triple_barrier_config=YieldTripleBarrierConfig(
                stop_loss=Decimal("0.05"),
                apr_yield=Decimal("3.65"),
                time_limit=60,
                stop_loss_order_type=OrderType.MARKET,
            ),
        )

    @staticmethod
    def get_progressive_config_market_short():
        return ProgressiveExecutorConfig(
            id="test-2",
            timestamp=1234567890,
            trading_pair="ETH-USDT",
            connector_name="binance",
            side=TradeType.SELL,
            entry_price=Decimal("100"),
            amount=Decimal("1"),
            triple_barrier_config=YieldTripleBarrierConfig(
                stop_loss=Decimal("0.05"),
                apr_yield=Decimal("3.65"),
                time_limit=60,
                stop_loss_order_type=OrderType.MARKET,
            ),
        )

    @staticmethod
    def get_incomplete_progressive_config():
        return ProgressiveExecutorConfig(
            id="test-3",
            timestamp=1234567890,
            trading_pair="ETH-USDT",
            connector_name="binance",
            side=TradeType.SELL,
            entry_price=Decimal("100"),
            amount=Decimal("1"),
            triple_barrier_config=YieldTripleBarrierConfig(stop_loss_order_type=OrderType.MARKET),
        )

    def test_properties(self):
        progressive_config = self.get_progressive_config_market_short()
        progressive_executor = ProgressiveExecutor(self.strategy, progressive_config)
        self.assertEqual(progressive_executor.trade_pnl_quote, Decimal("0"))
        progressive_executor._status = RunnableStatus.TERMINATED
        self.assertTrue(progressive_executor.is_closed)
        self.assertEqual(progressive_executor.config.trading_pair, "ETH-USDT")
        self.assertEqual(progressive_executor.config.connector_name, "binance")
        self.assertEqual(progressive_executor.config.side, TradeType.SELL)
        self.assertEqual(progressive_executor.entry_price, Decimal("100"))
        self.assertEqual(progressive_executor.config.amount, Decimal("1"))
        self.assertEqual(progressive_executor.end_time, 1234567890 + 60)
        self.assertEqual(progressive_executor.config.triple_barrier_config.stop_loss_order_type, OrderType.MARKET)
        self.assertEqual(progressive_executor.config.triple_barrier_config.time_limit_order_type, OrderType.MARKET)
        self.assertEqual(progressive_executor.open_filled_amount, Decimal("0"))
        self.assertEqual(progressive_executor.config.triple_barrier_config.trailing_stop, None)
        self.assertEqual(progressive_executor.config.triple_barrier_config.trailing_stop_order_type, OrderType.LIMIT)
        self.assertIsInstance(progressive_executor.logger(), HummingbotLogger)

    def get_progressive_executor_running_from_config(self, progressive_config):
        progressive_executor = ProgressiveExecutor(self.strategy, progressive_config)
        progressive_executor._status = RunnableStatus.RUNNING
        return progressive_executor

    @patch.object(ProgressiveExecutor, "get_price")
    async def test_control_position_create_open_order(self, mock_price):
        mock_price.return_value = Decimal("100")
        progressive_config = self.get_progressive_config_market_short()
        progressive_executor = self.get_progressive_executor_running_from_config(progressive_config)
        await progressive_executor.control_task()
        self.assertEqual(progressive_executor._open_order.order_id, "OID-SELL-1")

    @patch.object(ProgressiveExecutor, "validate_sufficient_balance")
    @patch.object(ProgressiveExecutor, "get_trading_rules")
    @patch.object(ProgressiveExecutor, "get_price")
    async def test_control_position_not_started_expired(self, mock_price, trading_rules_mock, _):
        mock_price.return_value = Decimal("100")
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules_mock.return_value = trading_rules
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890 + 61)
        progressive_config = self.get_progressive_config_market_short()
        progressive_executor = ProgressiveExecutor(self.strategy, progressive_config)
        await progressive_executor.control_loop()
        self.assertIsNone(progressive_executor._open_order)
        self.assertEqual(progressive_executor.close_type, CloseType.EXPIRED)
        self.assertEqual(progressive_executor.trade_pnl_pct, Decimal("0"))

    @patch.object(ProgressiveExecutor, "get_trading_rules")
    async def test_control_open_order_expiration(self, trading_rules_mock):
        progressive_config = self.get_progressive_config_market_short()
        progressive_executor = self.get_progressive_executor_running_from_config(progressive_config)
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules_mock.return_value = trading_rules
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890 + 61)
        progressive_executor._open_order = TrackedOrder(order_id="OID-SELL-1")
        progressive_executor._open_order.order = InFlightOrder(
            client_order_id="OID-SELL-1",
            exchange_order_id="EOID4",
            trading_pair=progressive_config.trading_pair,
            order_type=progressive_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.SELL,
            amount=progressive_config.amount,
            price=progressive_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN,
        )
        await progressive_executor.control_task()
        progressive_executor._strategy.cancel.assert_called_with(
            connector_name="binance", trading_pair="ETH-USDT", order_id="OID-SELL-1"
        )
        self.assertEqual(progressive_executor.trade_pnl_pct, Decimal("0"))

    async def test_control_position_order_placed_not_cancel_open_order(self):
        progressive_config = self.get_progressive_config_market_short()
        progressive_executor = self.get_progressive_executor_running_from_config(progressive_config)
        progressive_executor._open_order = TrackedOrder(order_id="OID-SELL-1")
        await progressive_executor.control_task()
        progressive_executor._strategy.cancel.assert_not_called()

    @patch(
        "hummingbot.strategy_v2.executors.progressive_executor.progressive_executor.ProgressiveExecutor.get_price",
        return_value=Decimal("101"),
    )
    async def test_control_position_active_position_create_take_profit(self, _):
        progressive_config = self.get_progressive_config_market_short()
        progressive_executor = self.get_progressive_executor_running_from_config(progressive_config)
        progressive_executor._open_order = TrackedOrder(order_id="OID-SELL-1")
        progressive_executor._open_order.order = InFlightOrder(
            client_order_id="OID-SELL-1",
            exchange_order_id="EOID4",
            trading_pair=progressive_config.trading_pair,
            order_type=progressive_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.SELL,
            amount=progressive_config.amount,
            price=progressive_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED,
        )
        progressive_executor._open_order.order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-SELL-1",
                exchange_order_id="EOID4",
                trading_pair=progressive_config.trading_pair,
                fill_price=progressive_config.entry_price,
                fill_base_amount=progressive_config.amount,
                fill_quote_amount=progressive_config.amount * progressive_config.entry_price,
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))]),
                fill_timestamp=10,
            )
        )
        await progressive_executor.control_task()
        self.assertEqual(progressive_executor.trade_pnl_pct, Decimal("-0.01"))

    @patch.object(ProgressiveExecutor, "get_trading_rules")
    @patch(
        "hummingbot.strategy_v2.executors.progressive_executor.progressive_executor.ProgressiveExecutor.get_price",
        return_value=Decimal("70"),
    )
    async def test_control_position_active_position_close_by_stop_loss(self, _, trading_rules_mock):
        progressive_config = self.get_progressive_config_market_long()
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules_mock.return_value = trading_rules
        progressive_executor = self.get_progressive_executor_running_from_config(progressive_config)
        progressive_executor._open_order = TrackedOrder(order_id="OID-BUY-1")
        progressive_executor._open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=progressive_config.trading_pair,
            order_type=progressive_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=progressive_config.amount,
            price=progressive_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED,
        )

        progressive_executor._open_order.order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-BUY-1",
                exchange_order_id="EOID4",
                trading_pair=progressive_config.trading_pair,
                fill_price=progressive_config.entry_price,
                fill_base_amount=progressive_config.amount,
                fill_quote_amount=progressive_config.amount * progressive_config.entry_price,
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))]),
                fill_timestamp=10,
            )
        )
        await progressive_executor.control_task()
        self.assertEqual(progressive_executor._close_order.order_id, "OID-SELL-1")
        self.assertEqual(progressive_executor.close_type, CloseType.STOP_LOSS)
        self.assertEqual(progressive_executor.trade_pnl_pct, Decimal("-0.3"))

    @patch.object(ProgressiveExecutor, "get_trading_rules")
    @patch(
        "hummingbot.strategy_v2.executors.progressive_executor.progressive_executor.ProgressiveExecutor.get_price",
        return_value=Decimal("100"),
    )
    async def test_control_position_active_position_close_by_time_limit(self, _, trading_rules_mock):
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules_mock.return_value = trading_rules
        progressive_config = self.get_progressive_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890 + 61)
        progressive_executor = self.get_progressive_executor_running_from_config(progressive_config)
        progressive_executor._open_order = TrackedOrder(order_id="OID-BUY-1")
        progressive_executor._open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=progressive_config.trading_pair,
            order_type=progressive_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=progressive_config.amount,
            price=progressive_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED,
        )
        progressive_executor._open_order.order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-BUY-1",
                exchange_order_id="EOID4",
                trading_pair=progressive_config.trading_pair,
                fill_price=progressive_config.entry_price,
                fill_base_amount=progressive_config.amount,
                fill_quote_amount=progressive_config.amount * progressive_config.entry_price,
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))]),
                fill_timestamp=10,
            )
        )

        await progressive_executor.control_task()
        self.assertEqual(progressive_executor._close_order.order_id, "OID-SELL-1")
        self.assertEqual(progressive_executor.close_type, CloseType.TIME_LIMIT)
        self.assertEqual(progressive_executor.trade_pnl_pct, Decimal("0.0"))

    @patch.object(ProgressiveExecutor, "get_trading_rules")
    @patch(
        "hummingbot.strategy_v2.executors.progressive_executor.progressive_executor.ProgressiveExecutor.get_price",
        return_value=Decimal("70"),
    )
    async def test_control_position_close_placed_stop_loss_failed(self, _, trading_rules_mock):
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules_mock.return_value = trading_rules
        progressive_config = self.get_progressive_config_market_long()
        progressive_executor = self.get_progressive_executor_running_from_config(progressive_config)
        progressive_executor._open_order = TrackedOrder(order_id="OID-BUY-1")
        progressive_executor._open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=progressive_config.trading_pair,
            order_type=progressive_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=progressive_config.amount,
            price=progressive_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED,
        )
        fee: Decimal = Decimal("0.2")
        progressive_executor._open_order.order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-BUY-1",
                exchange_order_id="EOID4",
                trading_pair=progressive_config.trading_pair,
                fill_price=progressive_config.entry_price,
                fill_base_amount=progressive_config.amount,
                fill_quote_amount=progressive_config.amount * progressive_config.entry_price,
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=fee)]),
                fill_timestamp=10,
            )
        )

        progressive_executor._close_order = TrackedOrder("OID-SELL-FAIL")
        progressive_executor.close_type = CloseType.STOP_LOSS

        market = MagicMock()
        progressive_executor.process_order_failed_event(
            "102",
            market,
            MarketOrderFailureEvent(order_id="OID-SELL-FAIL", timestamp=1640001112.223, order_type=OrderType.MARKET),
        )
        await progressive_executor.control_task()
        self.assertEqual(progressive_executor._close_order.order_id, "OID-SELL-1")
        self.assertEqual(progressive_executor.close_type, CloseType.STOP_LOSS)

    def test_process_order_completed_event_open_order(self):
        progressive_config = self.get_progressive_config_market_long()
        progressive_executor = self.get_progressive_executor_running_from_config(progressive_config)
        progressive_executor._open_order = TrackedOrder("OID-BUY-1")
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=progressive_config.amount,
            quote_asset_amount=progressive_config.amount * progressive_config.entry_price,
            order_type=progressive_config.triple_barrier_config.open_order_type,
            exchange_order_id="ED140",
        )
        market = MagicMock()
        progressive_executor.process_order_completed_event("102", market, event)

    def test_process_order_completed_event_close_order(self):
        progressive_config = self.get_progressive_config_market_long()
        progressive_executor = self.get_progressive_executor_running_from_config(progressive_config)
        progressive_executor._close_order = TrackedOrder("OID-BUY-1")
        progressive_executor.close_type = CloseType.STOP_LOSS
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=progressive_config.amount,
            quote_asset_amount=progressive_config.amount * progressive_config.entry_price,
            order_type=progressive_config.triple_barrier_config.open_order_type,
            exchange_order_id="ED140",
        )
        market = MagicMock()
        progressive_executor.process_order_completed_event("102", market, event)
        self.assertEqual(progressive_executor.close_timestamp, 1234567890)
        self.assertEqual(progressive_executor.close_type, CloseType.STOP_LOSS)

    def test_process_order_canceled_event(self):
        progressive_config = self.get_progressive_config_market_long()
        progressive_executor = self.get_progressive_executor_running_from_config(progressive_config)
        progressive_executor._close_order = TrackedOrder("OID-BUY-1")
        event = OrderCancelledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
        )
        market = MagicMock()
        progressive_executor.process_order_canceled_event(102, market, event)
        self.assertEqual(progressive_executor._close_order, None)

    @patch(
        "hummingbot.strategy_v2.executors.progressive_executor.progressive_executor.ProgressiveExecutor.get_price",
        return_value=Decimal("101"),
    )
    def test_to_format_status(self, price_mock):
        progressive_config = self.get_progressive_config_market_long()
        progressive_executor = self.get_progressive_executor_running_from_config(progressive_config)
        progressive_executor._open_order = TrackedOrder("OID-BUY-1")
        progressive_executor._open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=progressive_config.trading_pair,
            order_type=progressive_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=progressive_config.amount,
            price=progressive_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED,
        )
        fee: Decimal = Decimal("0.2")
        progressive_executor._open_order.order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-BUY-1",
                exchange_order_id="EOID4",
                trading_pair=progressive_config.trading_pair,
                fill_price=progressive_config.entry_price,
                fill_base_amount=progressive_config.amount,
                fill_quote_amount=progressive_config.amount * progressive_config.entry_price,
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=fee)]),
                fill_timestamp=10,
            )
        )
        status = progressive_executor.to_format_status()
        # pnl: Decimal = (price_mock.return_value - progressive_config.entry_price) * 100 / progressive_config.entry_price
        self.assertTrue(any("ETH-USDT" in s for s in status))
        # self.assertTrue(any(f"{pnl:.3f}%" in s for s in status))

    @patch(
        "hummingbot.strategy_v2.executors.progressive_executor.progressive_executor.ProgressiveExecutor.get_price",
        return_value=Decimal("101"),
    )
    def test_to_format_status_is_closed(self, price_mock):
        progressive_config = self.get_progressive_config_market_long()
        progressive_executor = self.get_progressive_executor_running_from_config(progressive_config)
        progressive_executor._open_order = TrackedOrder("OID-BUY-1")
        progressive_executor._open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=progressive_config.trading_pair,
            order_type=progressive_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=progressive_config.amount,
            price=progressive_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED,
        )
        fee: Decimal = Decimal("0.2")
        progressive_executor._open_order.order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-BUY-1",
                exchange_order_id="EOID4",
                trading_pair=progressive_config.trading_pair,
                fill_price=progressive_config.entry_price,
                fill_base_amount=progressive_config.amount,
                fill_quote_amount=progressive_config.amount * progressive_config.entry_price,
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=fee)]),
                fill_timestamp=10,
            )
        )
        status = progressive_executor.to_format_status()
        # pnl: Decimal = (price_mock.return_value - progressive_config.entry_price) * 100 / progressive_config.entry_price
        self.assertTrue(any("ETH-USDT" in s for s in status))
        # print(status)
        # self.assertTrue(any(f"{pnl:.3f}%" in s for s in status))

    @patch.object(ProgressiveExecutor, "get_trading_rules")
    @patch.object(ProgressiveExecutor, "adjust_order_candidates")
    async def test_validate_sufficient_balance(self, mock_adjust_order_candidates, mock_get_trading_rules):
        # Mock trading rules
        trading_rules = TradingRule(
            trading_pair="ETH-USDT",
            min_order_size=Decimal("0.1"),
            min_price_increment=Decimal("0.1"),
            min_base_amount_increment=Decimal("0.1"),
        )
        mock_get_trading_rules.return_value = trading_rules
        executor = ProgressiveExecutor(self.strategy, self.get_progressive_config_market_long())
        # Mock order candidate
        order_candidate = OrderCandidate(
            trading_pair="ETH-USDT",
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
        )
        # Test for sufficient balance
        mock_adjust_order_candidates.return_value = [order_candidate]
        await executor.validate_sufficient_balance()
        self.assertNotEqual(executor.close_type, CloseType.INSUFFICIENT_BALANCE)

        # Test for insufficient balance
        order_candidate.amount = Decimal("0")
        mock_adjust_order_candidates.return_value = [order_candidate]
        await executor.validate_sufficient_balance()
        self.assertEqual(executor.close_type, CloseType.INSUFFICIENT_BALANCE)
        self.assertEqual(executor.status, RunnableStatus.TERMINATED)

    def test_get_custom_info(self):
        progressive_config = self.get_progressive_config_market_long()
        executor = ProgressiveExecutor(self.strategy, progressive_config)
        custom_info = executor.get_custom_info()

        self.assertEqual(custom_info["level_id"], progressive_config.level_id)
        self.assertEqual(custom_info["current_position_average_price"], executor.entry_price)
        self.assertEqual(custom_info["side"], progressive_config.side)
        self.assertEqual(custom_info["current_retries"], executor._current_retries)
        self.assertEqual(custom_info["max_retries"], executor._max_retries)

    def test_cancel_close_order_and_process_cancel_event(self):
        progressive_config = self.get_progressive_config_market_long()
        progressive_executor = self.get_progressive_executor_running_from_config(progressive_config)
        progressive_executor._close_order = TrackedOrder("OID-BUY-1")
        progressive_executor.cancel_close_order()
        event = OrderCancelledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
        )
        market = MagicMock()
        progressive_executor.process_order_canceled_event("102", market, event)
        self.assertEqual(progressive_executor.close_type, None)

    @patch(
        "hummingbot.strategy_v2.executors.progressive_executor.progressive_executor.ProgressiveExecutor.get_price",
        return_value=Decimal("101"),
    )
    def test_progressive_executor_created_without_entry_price(self, _):
        config = ProgressiveExecutorConfig(
            id="test",
            timestamp=1234567890,
            trading_pair="ETH-USDT",
            connector_name="binance",
            side=TradeType.BUY,
            amount=Decimal("1"),
            triple_barrier_config=YieldTripleBarrierConfig(
                stop_loss=Decimal("0.05"),
                apr_yield=Decimal("3.65"),
                time_limit=60,
                take_profit_order_type=OrderType.LIMIT,
                stop_loss_order_type=OrderType.MARKET,
            ),
        )

        executor = ProgressiveExecutor(self.strategy, config)
        self.assertEqual(executor.entry_price, Decimal("101"))

    @patch(
        "hummingbot.strategy_v2.executors.progressive_executor.progressive_executor.ProgressiveExecutor.get_price",
        return_value=Decimal("101"),
    )
    def test_progressive_executor_entry_price_updated_with_limit_maker(self, _):
        config = ProgressiveExecutorConfig(
            id="test",
            timestamp=1234567890,
            trading_pair="ETH-USDT",
            connector_name="binance",
            side=TradeType.BUY,
            amount=Decimal("1"),
            entry_price=Decimal("102"),
            triple_barrier_config=YieldTripleBarrierConfig(
                open_order_type=OrderType.LIMIT_MAKER,
                stop_loss=Decimal("0.05"),
                apr_yield=Decimal("3.65"),
                time_limit=60,
                take_profit_order_type=OrderType.LIMIT,
                stop_loss_order_type=OrderType.MARKET,
            ),
        )

        executor = ProgressiveExecutor(self.strategy, config)
        self.assertEqual(executor.entry_price, Decimal("101"))

    def test_partial_close_order(self):
        """Test both partial and full close scenarios"""

        def mock_get_in_flight_order(
            amount,
            connector_name,
            order_id,
        ):
            in_flight_order = InFlightOrder(
                client_order_id=order_id,
                trading_pair="ETH-USDT",
                order_type=OrderType.MARKET,
                trade_type=TradeType.BUY,
                amount=amount,
                creation_timestamp=1234567890,
                price=Decimal("110"),
            )
            in_flight_order.executed_amount_base = amount
            return in_flight_order

        executor = ProgressiveExecutor(self.strategy, self.get_basic_config())
        executor.open_order = self._create_filled_order(Decimal("1"), Decimal("100"))

        # Test partial close
        executor.place_partial_close_order(
            close_type=CloseType.TRAILING_STOP,
            amount_to_close=Decimal("0.3"),
        )
        self.assertEqual(len(executor.realized_orders), 1)
        self.assertIsNone(executor.close_type)

        # Simulate fill event for the partial close
        fill_event = OrderFilledEvent(
            timestamp=1234567890,
            order_id=executor.realized_orders[0].order_id,
            trading_pair="ETH-USDT",
            trade_type=TradeType.BUY,  # Opposite of open order
            order_type=OrderType.MARKET,
            price=Decimal("110"),
            amount=Decimal("0.3"),
            trade_fee=AddedToCostTradeFee(flat_fees=[TokenAmount("USDT", Decimal("0.1"))]),
        )
        executor.get_in_flight_order = partial(mock_get_in_flight_order, Decimal("0.3"))
        executor.process_order_filled_event(None, None, fill_event)

        # Verify updated amounts
        self.assertEqual(executor.realized_orders[0].executed_amount_base, Decimal("0.3"))

        # Test full close conversion
        executor.place_partial_close_order(
            close_type=CloseType.TRAILING_STOP,
            amount_to_close=Decimal("0.8"),
        )
        self.assertEqual(executor.close_type, CloseType.TRAILING_STOP)

    def test_yield_based_expiry(self):
        """Test time expiry considering APR yield"""
        executor = ProgressiveExecutor(self.strategy, self.get_basic_config())
        executor.open_order = self._create_filled_order(Decimal("1"), Decimal("100"))

        # Test expiry below target yield
        with patch.object(executor, "get_net_pnl_pct", return_value=Decimal("0.001")):
            with patch(
                "hummingbot.strategy_v2.executors.progressive_executor.progressive_executor.ProgressiveExecutor.is_expired",
                new_callable=PropertyMock,
            ) as mock_is_expired:
                mock_is_expired.return_value = True
                self.assertTrue(executor.is_extended_on_yield)
