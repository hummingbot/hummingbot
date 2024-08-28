from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock, PropertyMock, patch

from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, TradeUpdate
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.event.events import BuyOrderCompletedEvent, MarketOrderFailureEvent, OrderCancelledEvent
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.executors.position_executor.position_executor import PositionExecutor
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class TestPositionExecutor(IsolatedAsyncioWrapperTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.strategy = self.create_mock_strategy

    @property
    def create_mock_strategy(self):
        market = MagicMock()
        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock(spec=ScriptStrategyBase)
        type(strategy).market_info = PropertyMock(return_value=market_info)
        type(strategy).trading_pair = PropertyMock(return_value="ETH-USDT")
        type(strategy).current_timestamp = PropertyMock(return_value=1234567890)
        strategy.buy.side_effect = ["OID-BUY-1", "OID-BUY-2", "OID-BUY-3"]
        strategy.sell.side_effect = ["OID-SELL-1", "OID-SELL-2", "OID-SELL-3"]
        strategy.cancel.return_value = None
        strategy.connectors = {
            "binance": MagicMock(spec=ExchangePyBase),
        }
        return strategy

    def get_position_config_market_long(self):
        return PositionExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT",
                                      connector_name="binance",
                                      side=TradeType.BUY, entry_price=Decimal("100"), amount=Decimal("1"),
                                      triple_barrier_config=TripleBarrierConfig(
                                          stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60,
                                          take_profit_order_type=OrderType.LIMIT,
                                          stop_loss_order_type=OrderType.MARKET))

    def get_position_config_market_long_tp_market(self):
        return PositionExecutorConfig(id="test-1", timestamp=1234567890, trading_pair="ETH-USDT",
                                      connector_name="binance",
                                      side=TradeType.BUY, entry_price=Decimal("100"), amount=Decimal("1"),
                                      triple_barrier_config=TripleBarrierConfig(
                                          stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60,
                                          take_profit_order_type=OrderType.MARKET,
                                          stop_loss_order_type=OrderType.MARKET))

    def get_position_config_market_short(self):
        return PositionExecutorConfig(id="test-2", timestamp=1234567890, trading_pair="ETH-USDT",
                                      connector_name="binance",
                                      side=TradeType.SELL, entry_price=Decimal("100"), amount=Decimal("1"),
                                      triple_barrier_config=TripleBarrierConfig(
                                          stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60,
                                          take_profit_order_type=OrderType.LIMIT,
                                          stop_loss_order_type=OrderType.MARKET))

    def get_incomplete_position_config(self):
        return PositionExecutorConfig(id="test-3", timestamp=1234567890, trading_pair="ETH-USDT",
                                      connector_name="binance",
                                      side=TradeType.SELL, entry_price=Decimal("100"), amount=Decimal("1"),
                                      triple_barrier_config=TripleBarrierConfig(
                                          take_profit_order_type=OrderType.LIMIT,
                                          stop_loss_order_type=OrderType.MARKET))

    def test_properties(self):
        position_config = self.get_position_config_market_short()
        position_executor = PositionExecutor(self.strategy, position_config)
        self.assertEqual(position_executor.trade_pnl_quote, Decimal("0"))
        position_executor._status = RunnableStatus.TERMINATED
        self.assertTrue(position_executor.is_closed)
        self.assertEqual(position_executor.config.trading_pair, "ETH-USDT")
        self.assertEqual(position_executor.config.connector_name, "binance")
        self.assertEqual(position_executor.config.side, TradeType.SELL)
        self.assertEqual(position_executor.entry_price, Decimal("100"))
        self.assertEqual(position_executor.config.amount, Decimal("1"))
        self.assertEqual(position_executor.take_profit_price, Decimal("90.0"))
        self.assertEqual(position_executor.end_time, 1234567890 + 60)
        self.assertEqual(position_executor.config.triple_barrier_config.take_profit_order_type, OrderType.LIMIT)
        self.assertEqual(position_executor.config.triple_barrier_config.stop_loss_order_type, OrderType.MARKET)
        self.assertEqual(position_executor.config.triple_barrier_config.time_limit_order_type, OrderType.MARKET)
        self.assertEqual(position_executor.open_filled_amount, Decimal("0"))
        self.assertEqual(position_executor.config.triple_barrier_config.trailing_stop, None)
        self.assertIsInstance(position_executor.logger(), HummingbotLogger)

    def get_position_executor_running_from_config(self, position_config):
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor._status = RunnableStatus.RUNNING
        return position_executor

    @patch.object(PositionExecutor, "get_trading_rules")
    @patch.object(PositionExecutor, "get_price")
    async def test_control_position_create_open_order(self, mock_price, trading_rules_mock):
        mock_price.return_value = Decimal("100")
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules_mock.return_value = trading_rules
        position_config = self.get_position_config_market_short()
        position_executor = self.get_position_executor_running_from_config(position_config)
        await position_executor.control_task()
        self.assertEqual(position_executor._open_order.order_id, "OID-SELL-1")

    @patch.object(PositionExecutor, "validate_sufficient_balance")
    @patch.object(PositionExecutor, "get_trading_rules")
    @patch.object(PositionExecutor, "get_price")
    async def test_control_position_not_started_expired(self, mock_price, trading_rules_mock, _):
        mock_price.return_value = Decimal("100")
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules_mock.return_value = trading_rules
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890 + 61)
        position_config = self.get_position_config_market_short()
        position_executor = PositionExecutor(self.strategy, position_config)
        await position_executor.control_loop()
        self.assertIsNone(position_executor._open_order)
        self.assertEqual(position_executor.close_type, CloseType.EXPIRED)
        self.assertEqual(position_executor.trade_pnl_pct, Decimal("0"))

    @patch.object(PositionExecutor, "get_trading_rules")
    async def test_control_open_order_expiration(self, trading_rules_mock):
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules.min_notional_size = Decimal("1")
        trading_rules_mock.return_value = trading_rules
        position_config = self.get_position_config_market_short()
        position_executor = self.get_position_executor_running_from_config(position_config)
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890 + 61)
        position_executor._open_order = TrackedOrder(order_id="OID-SELL-1")
        position_executor._open_order.order = InFlightOrder(
            client_order_id="OID-SELL-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.SELL,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN
        )
        await position_executor.control_task()
        position_executor._strategy.cancel.assert_called_with(
            connector_name="binance",
            trading_pair="ETH-USDT",
            order_id="OID-SELL-1")
        self.assertEqual(position_executor.trade_pnl_pct, Decimal("0"))

    @patch.object(PositionExecutor, "get_trading_rules")
    async def test_control_position_order_placed_not_cancel_open_order(self, trading_rules_mock):
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules.min_notional_size = Decimal("1")
        trading_rules_mock.return_value = trading_rules
        position_config = self.get_position_config_market_short()
        position_executor = self.get_position_executor_running_from_config(position_config)
        position_executor._open_order = TrackedOrder(order_id="OID-SELL-1")
        await position_executor.control_task()
        position_executor._strategy.cancel.assert_not_called()

    @patch.object(PositionExecutor, "get_trading_rules")
    @patch("hummingbot.strategy_v2.executors.position_executor.position_executor.PositionExecutor.get_price",
           return_value=Decimal("101"))
    async def test_control_position_active_position_create_take_profit(self, _, trading_rules_mock):
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules.min_notional_size = Decimal("1")
        trading_rules_mock.return_value = trading_rules
        position_config = self.get_position_config_market_short()
        position_executor = self.get_position_executor_running_from_config(position_config)
        position_executor._open_order = TrackedOrder(order_id="OID-SELL-1")
        position_executor._open_order.order = InFlightOrder(
            client_order_id="OID-SELL-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.SELL,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor._open_order.order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-SELL-1",
                exchange_order_id="EOID4",
                trading_pair=position_config.trading_pair,
                fill_price=position_config.entry_price,
                fill_base_amount=position_config.amount,
                fill_quote_amount=position_config.amount * position_config.entry_price,
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))]),
                fill_timestamp=10,
            )
        )
        await position_executor.control_task()
        self.assertEqual(position_executor._take_profit_limit_order.order_id, "OID-BUY-1")
        self.assertEqual(position_executor.trade_pnl_pct, Decimal("-0.01"))

    @patch.object(PositionExecutor, "get_trading_rules")
    @patch("hummingbot.strategy_v2.executors.position_executor.position_executor.PositionExecutor.get_price",
           return_value=Decimal("120"))
    async def test_control_position_active_position_close_by_take_profit_market(self, _, trading_rules_mock):
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules.min_notional_size = Decimal("1")
        trading_rules_mock.return_value = trading_rules
        position_config = self.get_position_config_market_long_tp_market()
        position_executor = self.get_position_executor_running_from_config(position_config)
        position_executor._open_order = TrackedOrder(order_id="OID-BUY-1")
        position_executor._open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )

        position_executor._open_order.order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-BUY-1",
                exchange_order_id="EOID4",
                trading_pair=position_config.trading_pair,
                fill_price=position_config.entry_price,
                fill_base_amount=position_config.amount,
                fill_quote_amount=position_config.amount * position_config.entry_price,
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))]),
                fill_timestamp=10,
            )
        )
        await position_executor.control_task()
        self.assertEqual(position_executor._close_order.order_id, "OID-SELL-1")
        self.assertEqual(position_executor.close_type, CloseType.TAKE_PROFIT)
        self.assertEqual(position_executor.trade_pnl_pct, Decimal("0.2"))

    @patch.object(PositionExecutor, "get_trading_rules")
    @patch("hummingbot.strategy_v2.executors.position_executor.position_executor.PositionExecutor.get_price",
           return_value=Decimal("70"))
    async def test_control_position_active_position_close_by_stop_loss(self, _, trading_rules_mock):
        position_config = self.get_position_config_market_long()
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules.min_notional_size = Decimal("1")
        trading_rules_mock.return_value = trading_rules
        position_executor = self.get_position_executor_running_from_config(position_config)
        position_executor._open_order = TrackedOrder(order_id="OID-BUY-1")
        position_executor._open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )

        position_executor._open_order.order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-BUY-1",
                exchange_order_id="EOID4",
                trading_pair=position_config.trading_pair,
                fill_price=position_config.entry_price,
                fill_base_amount=position_config.amount,
                fill_quote_amount=position_config.amount * position_config.entry_price,
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))]),
                fill_timestamp=10,
            )
        )
        await position_executor.control_task()
        self.assertEqual(position_executor._close_order.order_id, "OID-SELL-1")
        self.assertEqual(position_executor.close_type, CloseType.STOP_LOSS)
        self.assertEqual(position_executor.trade_pnl_pct, Decimal("-0.3"))

    @patch.object(PositionExecutor, "get_trading_rules")
    @patch("hummingbot.strategy_v2.executors.position_executor.position_executor.PositionExecutor.get_price",
           return_value=Decimal("100"))
    async def test_control_position_active_position_close_by_time_limit(self, _, trading_rules_mock):
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules.min_notional_size = Decimal("1")
        trading_rules_mock.return_value = trading_rules
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890 + 61)
        position_executor = self.get_position_executor_running_from_config(position_config)
        position_executor._open_order = TrackedOrder(order_id="OID-BUY-1")
        position_executor._open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor._open_order.order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-BUY-1",
                exchange_order_id="EOID4",
                trading_pair=position_config.trading_pair,
                fill_price=position_config.entry_price,
                fill_base_amount=position_config.amount,
                fill_quote_amount=position_config.amount * position_config.entry_price,
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))]),
                fill_timestamp=10,
            )
        )

        await position_executor.control_task()
        self.assertEqual(position_executor._close_order.order_id, "OID-SELL-2")
        self.assertEqual(position_executor.close_type, CloseType.TIME_LIMIT)
        self.assertEqual(position_executor.trade_pnl_pct, Decimal("0.0"))

    @patch.object(PositionExecutor, "get_trading_rules")
    @patch("hummingbot.strategy_v2.executors.position_executor.position_executor.PositionExecutor.get_price",
           return_value=Decimal("70"))
    async def test_control_position_close_placed_stop_loss_failed(self, _, trading_rules_mock):
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules.min_notional_size = Decimal("1")
        trading_rules_mock.return_value = trading_rules
        position_config = self.get_position_config_market_long()
        position_executor = self.get_position_executor_running_from_config(position_config)
        position_executor._open_order = TrackedOrder(order_id="OID-BUY-1")
        position_executor._open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor._open_order.order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-BUY-1",
                exchange_order_id="EOID4",
                trading_pair=position_config.trading_pair,
                fill_price=position_config.entry_price,
                fill_base_amount=position_config.amount,
                fill_quote_amount=position_config.amount * position_config.entry_price,
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))]),
                fill_timestamp=10,
            )
        )

        position_executor._close_order = TrackedOrder("OID-SELL-FAIL")
        position_executor.close_type = CloseType.STOP_LOSS
        market = MagicMock()
        position_executor.process_order_failed_event(
            "102", market, MarketOrderFailureEvent(
                order_id="OID-SELL-FAIL",
                timestamp=1640001112.223,
                order_type=OrderType.MARKET)
        )
        await position_executor.control_task()
        self.assertEqual(position_executor._close_order.order_id, "OID-SELL-1")
        self.assertEqual(position_executor.close_type, CloseType.STOP_LOSS)

    @patch.object(PositionExecutor, "get_in_flight_order")
    def test_process_order_completed_event_open_order(self, in_flight_order_mock):
        order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair="ETH-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=1640001112.223,
        )
        in_flight_order_mock.return_value = order
        position_config = self.get_position_config_market_long()
        position_executor = self.get_position_executor_running_from_config(position_config)
        position_executor._open_order = TrackedOrder("OID-BUY-1")
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=position_config.amount,
            quote_asset_amount=position_config.amount * position_config.entry_price,
            order_type=position_config.triple_barrier_config.open_order_type,
            exchange_order_id="ED140"
        )
        market = MagicMock()
        position_executor.process_order_completed_event("102", market, event)
        self.assertEqual(position_executor._open_order.order, order)

    @patch.object(PositionExecutor, "get_in_flight_order")
    def test_process_order_completed_event_close_order(self, mock_in_flight_order):
        order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair="ETH-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=1640001112.223,
        )
        mock_in_flight_order.return_value = order
        position_config = self.get_position_config_market_long()
        position_executor = self.get_position_executor_running_from_config(position_config)
        position_executor._close_order = TrackedOrder("OID-BUY-1")
        position_executor.close_type = CloseType.STOP_LOSS
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=position_config.amount,
            quote_asset_amount=position_config.amount * position_config.entry_price,
            order_type=position_config.triple_barrier_config.open_order_type,
            exchange_order_id="ED140"
        )
        market = MagicMock()
        position_executor.process_order_completed_event("102", market, event)
        self.assertEqual(position_executor.close_type, CloseType.STOP_LOSS)
        self.assertEqual(position_executor._close_order.order, order)

    @patch.object(PositionExecutor, "get_in_flight_order")
    def test_process_order_completed_event_take_profit_order(self, in_flight_order_mock):
        order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair="ETH-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=1640001112.223,
        )
        in_flight_order_mock.return_value = order
        position_config = self.get_position_config_market_long()
        position_executor = self.get_position_executor_running_from_config(position_config)
        position_executor._take_profit_limit_order = TrackedOrder("OID-BUY-1")
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=position_config.amount,
            quote_asset_amount=position_config.amount * position_config.entry_price,
            order_type=position_config.triple_barrier_config.open_order_type,
            exchange_order_id="ED140"
        )
        market = MagicMock()
        position_executor.process_order_completed_event("102", market, event)
        self.assertEqual(position_executor.close_type, CloseType.TAKE_PROFIT)
        self.assertEqual(position_executor._take_profit_limit_order.order, order)

    def test_process_order_canceled_event(self):
        position_config = self.get_position_config_market_long()
        position_executor = self.get_position_executor_running_from_config(position_config)
        position_executor._close_order = TrackedOrder("OID-BUY-1")
        event = OrderCancelledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
        )
        market = MagicMock()
        position_executor.process_order_canceled_event(102, market, event)
        self.assertEqual(position_executor._close_order, None)

    @patch("hummingbot.strategy_v2.executors.position_executor.position_executor.PositionExecutor.get_price",
           return_value=Decimal("101"))
    def test_to_format_status(self, _):
        position_config = self.get_position_config_market_long()
        position_executor = self.get_position_executor_running_from_config(position_config)
        position_executor._open_order = TrackedOrder("OID-BUY-1")
        position_executor._open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor._open_order.order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-BUY-1",
                exchange_order_id="EOID4",
                trading_pair=position_config.trading_pair,
                fill_price=position_config.entry_price,
                fill_base_amount=position_config.amount,
                fill_quote_amount=position_config.amount * position_config.entry_price,
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))]),
                fill_timestamp=10,
            )
        )
        status = position_executor.to_format_status()
        self.assertIn("Trading Pair: ETH-USDT", status[0])
        self.assertIn("PNL (%): 0.80%", status[0])

    @patch("hummingbot.strategy_v2.executors.position_executor.position_executor.PositionExecutor.get_price",
           return_value=Decimal("101"))
    def test_to_format_status_is_closed(self, _):
        position_config = self.get_position_config_market_long()
        position_executor = self.get_position_executor_running_from_config(position_config)
        position_executor._open_order = TrackedOrder("OID-BUY-1")
        position_executor._open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor._open_order.order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-BUY-1",
                exchange_order_id="EOID4",
                trading_pair=position_config.trading_pair,
                fill_price=position_config.entry_price,
                fill_base_amount=position_config.amount,
                fill_quote_amount=position_config.amount * position_config.entry_price,
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))]),
                fill_timestamp=10,
            )
        )
        type(position_executor).close_price = PropertyMock(return_value=Decimal(101))
        status = position_executor.to_format_status()
        self.assertIn("Trading Pair: ETH-USDT", status[0])
        self.assertIn("PNL (%): 0.80%", status[0])

    @patch.object(PositionExecutor, 'get_trading_rules')
    @patch.object(PositionExecutor, 'adjust_order_candidates')
    def test_validate_sufficient_balance(self, mock_adjust_order_candidates, mock_get_trading_rules):
        # Mock trading rules
        trading_rules = TradingRule(trading_pair="ETH-USDT", min_order_size=Decimal("0.1"),
                                    min_price_increment=Decimal("0.1"), min_base_amount_increment=Decimal("0.1"))
        mock_get_trading_rules.return_value = trading_rules
        executor = PositionExecutor(self.strategy, self.get_position_config_market_long())
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

    def test_get_custom_info(self):
        position_config = self.get_position_config_market_long()
        executor = PositionExecutor(self.strategy, position_config)
        custom_info = executor.get_custom_info()

        self.assertEqual(custom_info["level_id"], position_config.level_id)
        self.assertEqual(custom_info["current_position_average_price"], executor.entry_price)
        self.assertEqual(custom_info["side"], position_config.side)
        self.assertEqual(custom_info["current_retries"], executor._current_retries)
        self.assertEqual(custom_info["max_retries"], executor._max_retries)

    def test_cancel_close_order_and_process_cancel_event(self):
        position_config = self.get_position_config_market_long()
        position_executor = self.get_position_executor_running_from_config(position_config)
        position_executor._close_order = TrackedOrder("OID-BUY-1")
        position_executor.cancel_close_order()
        event = OrderCancelledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
        )
        market = MagicMock()
        position_executor.process_order_canceled_event("102", market, event)
        self.assertEqual(position_executor.close_type, None)

    @patch("hummingbot.strategy_v2.executors.position_executor.position_executor.PositionExecutor.get_price",
           return_value=Decimal("101"))
    def test_position_executor_created_without_entry_price(self, _):
        config = PositionExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT",
                                        connector_name="binance",
                                        side=TradeType.BUY, amount=Decimal("1"),
                                        triple_barrier_config=TripleBarrierConfig(
                                            stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60,
                                            take_profit_order_type=OrderType.LIMIT,
                                            stop_loss_order_type=OrderType.MARKET))

        executor = PositionExecutor(self.strategy, config)
        self.assertEqual(executor.entry_price, Decimal("101"))

    @patch("hummingbot.strategy_v2.executors.position_executor.position_executor.PositionExecutor.get_price",
           return_value=Decimal("101"))
    def test_position_executor_entry_price_updated_with_limit_maker(self, _):
        config = PositionExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT",
                                        connector_name="binance",
                                        side=TradeType.BUY, amount=Decimal("1"),
                                        entry_price=Decimal("102"),
                                        triple_barrier_config=TripleBarrierConfig(
                                            open_order_type=OrderType.LIMIT_MAKER,
                                            stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60,
                                            take_profit_order_type=OrderType.LIMIT,
                                            stop_loss_order_type=OrderType.MARKET))

        executor = PositionExecutor(self.strategy, config)
        self.assertEqual(executor.entry_price, Decimal("101"))

    @patch.object(PositionExecutor, "place_close_order_and_cancel_open_orders")
    async def test_control_shutdown_process(self, place_order_mock):
        position_config = self.get_position_config_market_long()
        position_executor = self.get_position_executor_running_from_config(position_config)
        position_executor._open_order = TrackedOrder("OID-BUY-1")
        position_executor._open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor._open_order.order.update_with_trade_update(
            TradeUpdate(
                trade_id="1",
                client_order_id="OID-BUY-1",
                exchange_order_id="EOID4",
                trading_pair=position_config.trading_pair,
                fill_price=position_config.entry_price,
                fill_base_amount=position_config.amount,
                fill_quote_amount=position_config.amount * position_config.entry_price,
                fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))]),
                fill_timestamp=10,
            )
        )
        position_executor._status = RunnableStatus.SHUTTING_DOWN
        await position_executor.control_task()
        place_order_mock.assert_called_once()
        position_executor._close_order = TrackedOrder("OID-SELL-1")
        position_executor._close_order.order = InFlightOrder(
            client_order_id="OID-SELL-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.triple_barrier_config.open_order_type,
            trade_type=TradeType.SELL,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN
        )
        await position_executor.control_task()
