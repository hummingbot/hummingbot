from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock, PropertyMock, patch

from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, TradeUpdate
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    SellOrderCompletedEvent,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.position_exchange_executor.data_types import (
    PositionExchangeExecutorConfig,
    TripleBarrierConfig,
)
from hummingbot.strategy_v2.executors.position_exchange_executor.position_exchange_executor import (
    PositionExchangeExecutor,
)
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class TestPositionExchangeExecutor(IsolatedAsyncioWrapperTestCase):
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

    def get_position_config_market_default(self):
        return PositionExchangeExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT",
                                              connector_name="binance",
                                              side=TradeType.BUY, entry_price=Decimal("100"), amount=Decimal("1"),
                                              triple_barrier_config=TripleBarrierConfig(
                                                  stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60))

    def get_position_config_market_long(self):
        return PositionExchangeExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT",
                                              connector_name="binance",
                                              side=TradeType.BUY, entry_price=Decimal("100"), amount=Decimal("1"),
                                              triple_barrier_config=TripleBarrierConfig(
                                                  stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60,
                                                  take_profit_order_type=OrderType.LIMIT,
                                                  stop_loss_order_type=OrderType.MARKET))

    def get_position_config_market_long_tp_market(self):
        return PositionExchangeExecutorConfig(id="test-1", timestamp=1234567890, trading_pair="ETH-USDT",
                                              connector_name="binance",
                                              side=TradeType.BUY, entry_price=Decimal("100"), amount=Decimal("1"),
                                              triple_barrier_config=TripleBarrierConfig(
                                                  stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60,
                                                  take_profit_order_type=OrderType.MARKET,
                                                  stop_loss_order_type=OrderType.MARKET))

    def get_position_config_market_short(self):
        return PositionExchangeExecutorConfig(
            id="test-2", timestamp=1234567890, trading_pair="ETH-USDT",
            connector_name="binance",
            side=TradeType.SELL, entry_price=Decimal("100"), amount=Decimal("1"),
            triple_barrier_config=TripleBarrierConfig(
                stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60))

    def get_incomplete_position_config(self):
        return PositionExchangeExecutorConfig(id="test-3", timestamp=1234567890, trading_pair="ETH-USDT",
                                              connector_name="binance",
                                              side=TradeType.SELL, entry_price=Decimal("100"), amount=Decimal("1"),
                                              triple_barrier_config=TripleBarrierConfig())

    def test_properties(self):
        position_config = self.get_position_config_market_default()
        position_exchange_executor = PositionExchangeExecutor(self.strategy, position_config)
        self.assertEqual(position_exchange_executor.trade_pnl_quote, Decimal("0"))
        position_exchange_executor._status = RunnableStatus.TERMINATED
        self.assertTrue(position_exchange_executor.is_closed)
        self.assertEqual(position_exchange_executor.config.trading_pair, "ETH-USDT")
        self.assertEqual(position_exchange_executor.config.connector_name, "binance")
        self.assertEqual(position_exchange_executor.config.side, TradeType.BUY)
        self.assertEqual(position_exchange_executor.entry_price, Decimal("100"))
        self.assertEqual(position_exchange_executor.config.amount, Decimal("1"))
        self.assertEqual(position_exchange_executor.take_profit_price, Decimal("110.0"))
        self.assertEqual(position_exchange_executor.end_time, 1234567890 + 60)
        self.assertEqual(position_exchange_executor.config.triple_barrier_config.take_profit_order_type,
                         OrderType.TAKE_PROFIT)
        self.assertEqual(position_exchange_executor.config.triple_barrier_config.stop_loss_order_type,
                         OrderType.STOP_LOSS)
        self.assertEqual(position_exchange_executor.config.triple_barrier_config.time_limit_order_type,
                         OrderType.MARKET)
        self.assertEqual(position_exchange_executor.open_filled_amount, Decimal("0"))
        self.assertEqual(position_exchange_executor.config.triple_barrier_config.trailing_stop, None)
        self.assertIsInstance(position_exchange_executor.logger(), HummingbotLogger)

    def get_position_exchange_executor_running_from_config(self, position_config):
        position_exchange_executor = PositionExchangeExecutor(self.strategy, position_config)
        position_exchange_executor._status = RunnableStatus.RUNNING
        return position_exchange_executor

    @patch.object(PositionExchangeExecutor, "get_trading_rules")
    @patch.object(PositionExchangeExecutor, "get_price")
    async def test_control_position_create_open_order(self, mock_price, trading_rules_mock):
        mock_price.return_value = Decimal("100")
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules_mock.return_value = trading_rules
        position_config = self.get_position_config_market_short()
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        await position_exchange_executor.control_task()
        self.assertEqual(position_exchange_executor._open_order.order_id, "OID-SELL-1")
        self.assertEqual(position_exchange_executor._stop_loss_order, None)
        self.assertEqual(position_exchange_executor._take_profit_order, None)
        self.assertEqual(position_exchange_executor._close_order, None)
        self.assertEqual(position_exchange_executor._trailing_stop_order, None)

    @patch.object(PositionExchangeExecutor, "validate_sufficient_balance")
    @patch.object(PositionExchangeExecutor, "get_trading_rules")
    @patch.object(PositionExchangeExecutor, "get_price")
    async def test_control_position_not_started_expired(self, mock_price, trading_rules_mock, _):
        mock_price.return_value = Decimal("100")
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules_mock.return_value = trading_rules
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890 + 61)
        position_config = self.get_position_config_market_short()
        position_exchange_executor = PositionExchangeExecutor(self.strategy, position_config)
        await position_exchange_executor.control_loop()
        self.assertIsNone(position_exchange_executor._open_order)
        self.assertEqual(position_exchange_executor.close_type, CloseType.EXPIRED)
        self.assertEqual(position_exchange_executor.trade_pnl_pct, Decimal("0"))

    @patch.object(PositionExchangeExecutor, "get_trading_rules")
    async def test_control_open_order_expiration(self, trading_rules_mock):
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules.min_notional_size = Decimal("1")
        trading_rules_mock.return_value = trading_rules
        position_config = self.get_position_config_market_short()
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890 + 61)
        position_exchange_executor._open_order = TrackedOrder(order_id="OID-SELL-1")
        position_exchange_executor._open_order.order = InFlightOrder(
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
        await position_exchange_executor.control_task()
        position_exchange_executor._strategy.cancel.assert_called_with(
            connector_name="binance",
            trading_pair="ETH-USDT",
            order_id="OID-SELL-1")
        self.assertEqual(position_exchange_executor.trade_pnl_pct, Decimal("0"))

    @patch.object(PositionExchangeExecutor, "get_trading_rules")
    async def test_control_position_order_placed_not_cancel_open_order(self, trading_rules_mock):
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules.min_notional_size = Decimal("1")
        trading_rules_mock.return_value = trading_rules
        position_config = self.get_position_config_market_short()
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        position_exchange_executor._open_order = TrackedOrder(order_id="OID-SELL-1")
        await position_exchange_executor.control_task()
        position_exchange_executor._strategy.cancel.assert_not_called()

    @patch.object(PositionExchangeExecutor, "get_trading_rules")
    @patch(
        "hummingbot.strategy_v2.executors.position_exchange_executor.position_exchange_executor.PositionExchangeExecutor.get_price",
        return_value=Decimal("101"))
    async def test_control_position_active_position_create_take_profit(self, _, trading_rules_mock):
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules.min_notional_size = Decimal("1")
        trading_rules_mock.return_value = trading_rules
        position_config = self.get_position_config_market_short()
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        position_exchange_executor._open_order = TrackedOrder(order_id="OID-SELL-1")
        position_exchange_executor._open_order.order = InFlightOrder(
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
        position_exchange_executor._open_order.order.update_with_trade_update(
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
        await position_exchange_executor.control_task()
        self.assertEqual(position_exchange_executor._stop_loss_order.order_id, "OID-BUY-1")
        self.assertEqual(position_exchange_executor._take_profit_order.order_id, "OID-BUY-2")
        self.assertEqual(position_exchange_executor.trade_pnl_pct, Decimal("-0.01"))

    @patch.object(PositionExchangeExecutor, "get_trading_rules")
    @patch(
        "hummingbot.strategy_v2.executors.position_exchange_executor.position_exchange_executor.PositionExchangeExecutor.get_price",
        return_value=Decimal("100"))
    async def test_control_position_active_position_close_by_time_limit(self, _, trading_rules_mock):
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules.min_notional_size = Decimal("1")
        trading_rules_mock.return_value = trading_rules
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890 + 61)
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        position_exchange_executor._open_order = TrackedOrder(order_id="OID-BUY-1")
        position_exchange_executor._open_order.order = InFlightOrder(
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
        position_exchange_executor._open_order.order.update_with_trade_update(
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

        await position_exchange_executor.control_task()
        self.assertEqual(position_exchange_executor._close_order.order_id, "OID-SELL-3")
        self.assertEqual(position_exchange_executor.close_type, CloseType.TIME_LIMIT)
        self.assertEqual(position_exchange_executor.trade_pnl_pct, Decimal("0.0"))

    @patch.object(PositionExchangeExecutor, "get_trading_rules")
    @patch(
        "hummingbot.strategy_v2.executors.position_exchange_executor.position_exchange_executor.PositionExchangeExecutor.get_price",
        return_value=Decimal("70"))
    async def test_control_position_close_placed_stop_loss_failed(self, _, trading_rules_mock):
        trading_rules = MagicMock(spec=TradingRule)
        trading_rules.min_order_size = Decimal("0.1")
        trading_rules.min_notional_size = Decimal("1")
        trading_rules_mock.return_value = trading_rules
        position_config = self.get_position_config_market_long()
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        position_exchange_executor._open_order = TrackedOrder(order_id="OID-BUY-1")
        position_exchange_executor._open_order.order = InFlightOrder(
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
        position_exchange_executor._open_order.order.update_with_trade_update(
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

        position_exchange_executor._close_order = TrackedOrder("OID-SELL-FAIL")
        position_exchange_executor.close_type = CloseType.STOP_LOSS
        market = MagicMock()
        position_exchange_executor.process_order_failed_event(
            "102", market, MarketOrderFailureEvent(
                order_id="OID-SELL-FAIL",
                timestamp=1640001112.223,
                order_type=OrderType.MARKET)
        )
        await position_exchange_executor.control_task()
        self.assertEqual(position_exchange_executor._stop_loss_order.order_id, "OID-SELL-1")
        self.assertEqual(position_exchange_executor.close_type, CloseType.STOP_LOSS)

    @patch.object(PositionExchangeExecutor, "get_in_flight_order")
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
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        position_exchange_executor._open_order = TrackedOrder("OID-BUY-1")
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
        position_exchange_executor.process_order_completed_event("102", market, event)
        self.assertEqual(position_exchange_executor._open_order.order, order)

    @patch.object(PositionExchangeExecutor, "get_in_flight_order")
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
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        position_exchange_executor._close_order = TrackedOrder("OID-BUY-1")
        position_exchange_executor.close_type = CloseType.STOP_LOSS
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
        position_exchange_executor.process_order_completed_event("102", market, event)
        self.assertEqual(position_exchange_executor.close_type, CloseType.STOP_LOSS)
        self.assertEqual(position_exchange_executor._close_order.order, order)

    @patch.object(PositionExchangeExecutor, "get_in_flight_order")
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
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        position_exchange_executor._take_profit_order = TrackedOrder("OID-BUY-1")
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
        position_exchange_executor.process_order_completed_event("102", market, event)
        self.assertEqual(position_exchange_executor.close_type, CloseType.TAKE_PROFIT)
        self.assertEqual(position_exchange_executor._close_order.order, order)

    @patch.object(PositionExchangeExecutor, "get_in_flight_order")
    def test_process_order_completed_event_stop_loss_order(self, in_flight_order_mock):
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
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        position_exchange_executor._stop_loss_order = TrackedOrder("OID-BUY-1")
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
        position_exchange_executor.process_order_completed_event("102", market, event)
        self.assertEqual(position_exchange_executor.close_type, CloseType.STOP_LOSS)
        self.assertEqual(position_exchange_executor._close_order.order, order)

    def test_process_order_canceled_event(self):
        position_config = self.get_position_config_market_long()
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        position_exchange_executor._close_order = TrackedOrder("OID-BUY-1")
        event = OrderCancelledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
        )
        market = MagicMock()
        position_exchange_executor.process_order_canceled_event(102, market, event)
        self.assertEqual(position_exchange_executor._close_order, None)

    @patch(
        "hummingbot.strategy_v2.executors.position_exchange_executor.position_exchange_executor.PositionExchangeExecutor.get_price",
        return_value=Decimal("101"))
    def test_to_format_status(self, _):
        position_config = self.get_position_config_market_long()
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        position_exchange_executor._open_order = TrackedOrder("OID-BUY-1")
        position_exchange_executor._open_order.order = InFlightOrder(
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
        position_exchange_executor._open_order.order.update_with_trade_update(
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
        status = position_exchange_executor.to_format_status()
        self.assertIn("Trading Pair: ETH-USDT", status[0])
        self.assertIn("PNL (%): 0.80%", status[0])

    @patch(
        "hummingbot.strategy_v2.executors.position_exchange_executor.position_exchange_executor.PositionExchangeExecutor.get_price",
        return_value=Decimal("101"))
    def test_to_format_status_is_closed(self, _):
        position_config = self.get_position_config_market_long()
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        position_exchange_executor._open_order = TrackedOrder("OID-BUY-1")
        position_exchange_executor._open_order.order = InFlightOrder(
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
        position_exchange_executor._open_order.order.update_with_trade_update(
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
        type(position_exchange_executor).close_price = PropertyMock(return_value=Decimal(101))
        status = position_exchange_executor.to_format_status()
        self.assertIn("Trading Pair: ETH-USDT", status[0])
        self.assertIn("PNL (%): 0.80%", status[0])

    @patch.object(PositionExchangeExecutor, 'get_trading_rules')
    @patch.object(PositionExchangeExecutor, 'adjust_order_candidates')
    def test_validate_sufficient_balance(self, mock_adjust_order_candidates, mock_get_trading_rules):
        # Mock trading rules
        trading_rules = TradingRule(trading_pair="ETH-USDT", min_order_size=Decimal("0.1"),
                                    min_price_increment=Decimal("0.1"), min_base_amount_increment=Decimal("0.1"))
        mock_get_trading_rules.return_value = trading_rules
        executor = PositionExchangeExecutor(self.strategy, self.get_position_config_market_long())
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
        executor = PositionExchangeExecutor(self.strategy, position_config)
        custom_info = executor.get_custom_info()

        self.assertEqual(custom_info["level_id"], position_config.level_id)
        self.assertEqual(custom_info["current_position_average_price"], executor.entry_price)
        self.assertEqual(custom_info["side"], position_config.side)
        self.assertEqual(custom_info["current_retries"], executor._current_retries)
        self.assertEqual(custom_info["max_retries"], executor._max_retries)

    def test_cancel_close_order_and_process_cancel_event(self):
        position_config = self.get_position_config_market_long()
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        position_exchange_executor._close_order = TrackedOrder("OID-BUY-1")
        position_exchange_executor.cancel_close_order()
        event = OrderCancelledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
        )
        market = MagicMock()
        position_exchange_executor.process_order_canceled_event("102", market, event)
        self.assertEqual(position_exchange_executor.close_type, None)

    @patch(
        "hummingbot.strategy_v2.executors.position_exchange_executor.position_exchange_executor.PositionExchangeExecutor.get_price",
        return_value=Decimal("101"))
    def test_position_exchange_executor_created_without_entry_price(self, _):
        config = PositionExchangeExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT",
                                                connector_name="binance",
                                                side=TradeType.BUY, amount=Decimal("1"),
                                                triple_barrier_config=TripleBarrierConfig(
                                                    stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"),
                                                    time_limit=60,
                                                    take_profit_order_type=OrderType.LIMIT,
                                                    stop_loss_order_type=OrderType.MARKET))

        executor = PositionExchangeExecutor(self.strategy, config)
        self.assertEqual(executor.entry_price, Decimal("101"))

    @patch(
        "hummingbot.strategy_v2.executors.position_exchange_executor.position_exchange_executor.PositionExchangeExecutor.get_price",
        return_value=Decimal("101"))
    def test_position_exchange_executor_entry_price_updated_with_limit_maker(self, _):
        config = PositionExchangeExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT",
                                                connector_name="binance",
                                                side=TradeType.BUY, amount=Decimal("1"),
                                                entry_price=Decimal("102"),
                                                triple_barrier_config=TripleBarrierConfig(
                                                    open_order_type=OrderType.LIMIT_MAKER,
                                                    stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"),
                                                    time_limit=60,
                                                    take_profit_order_type=OrderType.LIMIT,
                                                    stop_loss_order_type=OrderType.MARKET))

        executor = PositionExchangeExecutor(self.strategy, config)
        self.assertEqual(executor.entry_price, Decimal("101"))

    @patch.object(PositionExchangeExecutor, "get_in_flight_order")
    @patch.object(PositionExchangeExecutor, "place_close_order_and_cancel_open_orders")
    async def test_control_shutdown_process(self, place_order_mock, mock_in_flight_order):
        position_config = self.get_position_config_market_long()
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        position_exchange_executor._open_order = TrackedOrder("OID-BUY-1")
        position_exchange_executor._open_order.order = InFlightOrder(
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
        position_exchange_executor._open_order.order.update_with_trade_update(
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
        position_exchange_executor._status = RunnableStatus.SHUTTING_DOWN
        order = InFlightOrder(
            client_order_id="OID-SELL-1",
            exchange_order_id="EOID5",
            trading_pair="ETH-USDT",
            order_type=OrderType.STOP_LOSS,
            trade_type=TradeType.SELL,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=1640001112.223,
        )
        mock_in_flight_order.return_value = order
        position_exchange_executor._stop_loss_order = TrackedOrder("OID-SELL-1")
        event = SellOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-SELL-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=position_config.amount,
            quote_asset_amount=position_config.amount * position_config.entry_price,
            order_type=position_config.triple_barrier_config.stop_loss_order_type,
            exchange_order_id="ED140"
        )
        market = MagicMock()
        position_exchange_executor.process_order_completed_event("102", market, event)
        await position_exchange_executor.control_task()
        place_order_mock.assert_not_called()
        position_exchange_executor._close_order = TrackedOrder("OID-SELL-1")
        position_exchange_executor._close_order.order = InFlightOrder(
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
        await position_exchange_executor.control_task()

    @patch.object(PositionExchangeExecutor, "get_price")
    def test_is_within_activation_bounds_long(self, mock_price):
        mock_price.return_value = Decimal("100")
        position_config = self.get_position_config_market_long()
        position_config.activation_bounds = [Decimal("0.001"), Decimal("0.01")]
        position_config.triple_barrier_config.open_order_type = OrderType.MARKET
        executor = PositionExchangeExecutor(self.strategy, position_config)
        self.assertTrue(executor._is_within_activation_bounds(Decimal("100.0"), TradeType.BUY, OrderType.MARKET))
        self.assertFalse(executor._is_within_activation_bounds(Decimal("101.0"), TradeType.BUY, OrderType.MARKET))
        self.assertTrue(executor._is_within_activation_bounds(Decimal("99.9"), TradeType.BUY, OrderType.LIMIT))
        self.assertFalse(executor._is_within_activation_bounds(Decimal("99.7"), TradeType.BUY, OrderType.LIMIT))

    @patch.object(PositionExchangeExecutor, "get_price")
    def test_is_within_activation_bounds_market_short(self, mock_price):
        mock_price.return_value = Decimal("100")
        position_config = self.get_position_config_market_short()
        position_config.activation_bounds = [Decimal("0.001"), Decimal("0.01")]
        position_config.triple_barrier_config.open_order_type = OrderType.MARKET
        executor = PositionExchangeExecutor(self.strategy, position_config)
        self.assertTrue(executor._is_within_activation_bounds(Decimal("100"), TradeType.SELL, OrderType.MARKET))
        self.assertFalse(executor._is_within_activation_bounds(Decimal("99.9"), TradeType.SELL, OrderType.MARKET))
        self.assertTrue(executor._is_within_activation_bounds(Decimal("100.1"), TradeType.SELL, OrderType.LIMIT))
        self.assertFalse(executor._is_within_activation_bounds(Decimal("100.3"), TradeType.SELL, OrderType.LIMIT))

    def test_failed_executor_info(self):
        position_config = self.get_position_config_market_short()
        position_exchange_executor = self.get_position_exchange_executor_running_from_config(position_config)
        position_exchange_executor.close_type = CloseType.FAILED
        type(position_exchange_executor).filled_amount_quote = PropertyMock(return_value=Decimal("0"))
        executor_info = position_exchange_executor.executor_info
        self.assertEqual(executor_info.close_type, CloseType.FAILED)
        self.assertEqual(executor_info.net_pnl_pct, Decimal("0"))
