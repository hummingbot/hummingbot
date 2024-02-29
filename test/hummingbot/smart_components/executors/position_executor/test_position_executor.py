from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock, PropertyMock, patch

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.smart_components.executors.position_executor.data_types import (
    PositionExecutorConfig,
    PositionExecutorStatus,
    TrailingStop,
)
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.models.executors import CloseType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


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
        strategy.buy.side_effect = ["OID-BUY-1", "OID-BUY-2", "OID-BUY-3"]
        strategy.sell.side_effect = ["OID-SELL-1", "OID-SELL-2", "OID-SELL-3"]
        strategy.cancel.return_value = None
        strategy.connectors = {
            "binance": MagicMock(spec=ConnectorBase),
        }
        return strategy

    def get_position_config_trailing_stop(self):
        return PositionExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                                      side=TradeType.BUY, entry_price=Decimal("100"), amount=Decimal("1"),
                                      stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60,
                                      take_profit_order_type=OrderType.LIMIT, stop_loss_order_type=OrderType.MARKET,
                                      trailing_stop=TrailingStop(activation_price=Decimal("0.02"),
                                                                 trailing_delta=Decimal("0.01")))

    def get_position_config_market_long(self):
        return PositionExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                                      side=TradeType.BUY, entry_price=Decimal("100"), amount=Decimal("1"),
                                      stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60,
                                      take_profit_order_type=OrderType.LIMIT, stop_loss_order_type=OrderType.MARKET, )

    def get_position_config_market_long_tp_market(self):
        return PositionExecutorConfig(id="test-1", timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                                      side=TradeType.BUY, entry_price=Decimal("100"), amount=Decimal("1"),
                                      stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60,
                                      take_profit_order_type=OrderType.MARKET, stop_loss_order_type=OrderType.MARKET, )

    def get_position_config_market_short(self):
        return PositionExecutorConfig(id="test-2", timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                                      side=TradeType.SELL, entry_price=Decimal("100"), amount=Decimal("1"),
                                      stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60,
                                      take_profit_order_type=OrderType.LIMIT, stop_loss_order_type=OrderType.MARKET, )

    def get_incomplete_position_config(self):
        return PositionExecutorConfig(id="test-3", timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                                      side=TradeType.SELL, entry_price=Decimal("100"), amount=Decimal("1"),
                                      take_profit_order_type=OrderType.LIMIT, stop_loss_order_type=OrderType.MARKET, )

    def test_init_raises_exception(self):
        position_config = self.get_incomplete_position_config()
        with self.assertRaises(ValueError):
            PositionExecutor(self.strategy, position_config)

    def test_properties(self):
        position_config = self.get_position_config_market_short()
        position_executor = PositionExecutor(self.strategy, position_config)
        self.assertEqual(position_executor.trade_pnl_quote, Decimal("0"))
        position_executor.executor_status = PositionExecutorStatus.COMPLETED
        position_executor.close_type = CloseType.EARLY_STOP
        self.assertTrue(position_executor.is_closed)
        self.assertEqual(position_executor.executor_status, PositionExecutorStatus.COMPLETED)
        self.assertEqual(position_executor.trading_pair, "ETH-USDT")
        self.assertEqual(position_executor.exchange, "binance")
        self.assertEqual(position_executor.side, TradeType.SELL)
        self.assertEqual(position_executor.entry_price, Decimal("100"))
        self.assertEqual(position_executor.amount, Decimal("1"))
        self.assertEqual(position_executor.stop_loss_price, Decimal("105.00"))
        self.assertEqual(position_executor.take_profit_price, Decimal("90.0"))
        self.assertEqual(position_executor.end_time, 1234567890 + 60)
        self.assertEqual(position_executor.take_profit_order_type, OrderType.LIMIT)
        self.assertEqual(position_executor.stop_loss_order_type, OrderType.MARKET)
        self.assertEqual(position_executor.time_limit_order_type, OrderType.MARKET)
        self.assertEqual(position_executor.filled_amount, Decimal("0"))
        self.assertEqual(position_executor.trailing_stop_config, None)
        self.assertEqual(position_executor.close_price, Decimal("0"))
        self.assertIsInstance(position_executor.logger(), HummingbotLogger)
        position_executor.stop()

    async def test_control_position_not_started_create_open_order(self):
        position_config = self.get_position_config_market_short()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        position_executor = PositionExecutor(self.strategy, position_config)
        await position_executor.control_task()
        self.assertEqual(position_executor.open_order.order_id, "OID-SELL-1")
        position_executor.stop()

    async def test_control_position_not_started_expired(self):
        position_config = self.get_position_config_market_short()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234569890)
        position_executor = PositionExecutor(self.strategy, position_config)
        await position_executor.control_task()
        self.assertIsNone(position_executor.open_order.order_id)
        self.assertEqual(position_executor.executor_status, PositionExecutorStatus.COMPLETED)
        self.assertEqual(position_executor.close_type, CloseType.EXPIRED)
        self.assertEqual(position_executor.trade_pnl, Decimal("0"))
        position_executor.stop()

    async def test_control_open_order_expiration(self):
        position_config = self.get_position_config_market_short()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234569890)
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.open_order.order_id = "OID-SELL-1"
        await position_executor.control_task()
        position_executor._strategy.cancel.assert_called_with(
            connector_name="binance",
            trading_pair="ETH-USDT",
            order_id="OID-SELL-1")
        self.assertEqual(position_executor.executor_status, PositionExecutorStatus.NOT_STARTED)
        self.assertEqual(position_executor.trade_pnl, Decimal("0"))
        position_executor.stop()

    async def test_control_position_order_placed_not_cancel_open_order(self):
        position_config = self.get_position_config_market_short()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.open_order.order_id = "OID-SELL-1"
        await position_executor.control_task()
        position_executor._strategy.cancel.assert_not_called()
        position_executor.stop()

    @patch("hummingbot.smart_components.executors.position_executor.position_executor.PositionExecutor.get_price", return_value=Decimal("101"))
    async def test_control_position_active_position_create_take_profit(self, _):
        position_config = self.get_position_config_market_short()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.open_order.order_id = "OID-SELL-1"
        position_executor.open_order.order = InFlightOrder(
            client_order_id="OID-SELL-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.open_order_type,
            trade_type=TradeType.SELL,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor.open_order.order.update_with_trade_update(
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
        position_executor.executor_status = PositionExecutorStatus.ACTIVE_POSITION
        await position_executor.control_task()
        self.assertEqual(position_executor.take_profit_order.order_id, "OID-BUY-1")
        self.assertEqual(position_executor.trade_pnl, Decimal("-0.01"))
        position_executor.stop()

    @patch("hummingbot.smart_components.executors.position_executor.position_executor.PositionExecutor.get_price",
           return_value=Decimal("120"))
    async def test_control_position_active_position_close_by_take_profit_market(self, _):
        position_config = self.get_position_config_market_long_tp_market()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.open_order.order_id = "OID-BUY-1"
        position_executor.open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )

        position_executor.open_order.order.update_with_trade_update(
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
        position_executor.executor_status = PositionExecutorStatus.ACTIVE_POSITION
        await position_executor.control_task()
        self.assertEqual(position_executor.close_order.order_id, "OID-SELL-1")
        self.assertEqual(position_executor.close_type, CloseType.TAKE_PROFIT)
        self.assertEqual(position_executor.trade_pnl, Decimal("0.2"))
        position_executor.stop()

    @patch("hummingbot.smart_components.executors.position_executor.position_executor.PositionExecutor.get_price", return_value=Decimal("70"))
    async def test_control_position_active_position_close_by_stop_loss(self, _):
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.open_order.order_id = "OID-BUY-1"
        position_executor.open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )

        position_executor.open_order.order.update_with_trade_update(
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
        position_executor.executor_status = PositionExecutorStatus.ACTIVE_POSITION
        await position_executor.control_task()
        self.assertEqual(position_executor.close_order.order_id, "OID-SELL-1")
        self.assertEqual(position_executor.close_type, CloseType.STOP_LOSS)
        self.assertEqual(position_executor.trade_pnl, Decimal("-0.3"))
        position_executor.stop()

    @patch("hummingbot.smart_components.executors.position_executor.position_executor.PositionExecutor.get_price", return_value=Decimal("100"))
    async def test_control_position_active_position_close_by_time_limit(self, _):
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234597890)
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.open_order.order_id = "OID-BUY-1"
        position_executor.open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor.open_order.order.update_with_trade_update(
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

        position_executor.executor_status = PositionExecutorStatus.ACTIVE_POSITION
        await position_executor.control_task()
        self.assertEqual(position_executor.close_order.order_id, "OID-SELL-2")
        self.assertEqual(position_executor.close_type, CloseType.TIME_LIMIT)
        self.assertEqual(position_executor.trade_pnl, Decimal("0.0"))
        position_executor.stop()

    @patch("hummingbot.smart_components.executors.position_executor.position_executor.PositionExecutor.get_price", return_value=Decimal("70"))
    async def test_control_position_close_placed_stop_loss_failed(self, _):
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.open_order.order_id = "OID-BUY-1"
        position_executor.open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor.open_order.order.update_with_trade_update(
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

        position_executor.close_order.order_id = "OID-SELL-FAIL"
        position_executor.close_type = CloseType.STOP_LOSS
        market = MagicMock()
        position_executor.process_order_failed_event(
            "102", market, MarketOrderFailureEvent(
                order_id="OID-SELL-FAIL",
                timestamp=1640001112.223,
                order_type=OrderType.MARKET)
        )
        await position_executor.control_task()
        self.assertEqual(position_executor.close_order.order_id, "OID-SELL-1")
        self.assertEqual(position_executor.close_type, CloseType.STOP_LOSS)
        position_executor.stop()

    def test_process_order_completed_event_open_order(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.open_order.order_id = "OID-BUY-1"
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=position_config.amount,
            quote_asset_amount=position_config.amount * position_config.entry_price,
            order_type=position_config.open_order_type,
            exchange_order_id="ED140"
        )
        market = MagicMock()
        position_executor.process_order_completed_event("102", market, event)
        self.assertEqual(position_executor.executor_status, PositionExecutorStatus.ACTIVE_POSITION)
        position_executor.stop()

    def test_process_order_completed_event_close_order(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.close_order.order_id = "OID-BUY-1"
        position_executor.close_type = CloseType.STOP_LOSS
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=position_config.amount,
            quote_asset_amount=position_config.amount * position_config.entry_price,
            order_type=position_config.open_order_type,
            exchange_order_id="ED140"
        )
        market = MagicMock()
        position_executor.process_order_completed_event("102", market, event)
        self.assertEqual(position_executor.close_timestamp, 1234567890)
        self.assertEqual(position_executor.close_type, CloseType.STOP_LOSS)
        self.assertEqual(position_executor.executor_status, PositionExecutorStatus.COMPLETED)
        position_executor.stop()

    def test_process_order_completed_event_take_profit_order(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.take_profit_order.order_id = "OID-BUY-1"
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=position_config.amount,
            quote_asset_amount=position_config.amount * position_config.entry_price,
            order_type=position_config.open_order_type,
            exchange_order_id="ED140"
        )
        market = MagicMock()
        position_executor.process_order_completed_event("102", market, event)
        self.assertEqual(position_executor.close_timestamp, 1234567890)
        self.assertEqual(position_executor.executor_status, PositionExecutorStatus.COMPLETED)
        self.assertEqual(position_executor.close_type, CloseType.TAKE_PROFIT)
        position_executor.stop()

    def test_process_order_filled_event_open_order_not_started(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.open_order.order_id = "OID-BUY-1"
        event = OrderFilledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            trading_pair="ETH-USDT",
            price=position_config.entry_price,
            amount=position_config.amount,
            order_type=position_config.open_order_type,
            trade_type=TradeType.SELL,
            trade_fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))])
        )
        market = MagicMock()
        position_executor.process_order_filled_event("102", market, event)
        self.assertEqual(position_executor.executor_status, PositionExecutorStatus.ACTIVE_POSITION)
        position_executor.stop()

    def test_process_order_filled_event_open_order_started(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.open_order.order_id = "OID-BUY-1"
        event = OrderFilledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            trading_pair="ETH-USDT",
            price=position_config.entry_price,
            amount=position_config.amount,
            order_type=position_config.open_order_type,
            trade_type=TradeType.SELL,
            trade_fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))])
        )
        market = MagicMock()
        position_executor.executor_status = PositionExecutorStatus.ACTIVE_POSITION
        position_executor.process_order_filled_event("102", market, event)
        self.assertEqual(position_executor.executor_status, PositionExecutorStatus.ACTIVE_POSITION)
        position_executor.stop()

    @patch("hummingbot.smart_components.executors.position_executor.position_executor.PositionExecutor.get_price", return_value=Decimal("101"))
    def test_to_format_status(self, _):
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.open_order.order_id = "OID-BUY-1"
        position_executor.open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor.open_order.order.update_with_trade_update(
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
        position_executor.executor_status = PositionExecutorStatus.ACTIVE_POSITION
        status = position_executor.to_format_status()
        self.assertIn("Trading Pair: ETH-USDT", status[0])
        self.assertIn("PNL (%): 0.80%", status[0])
        position_executor.stop()

    @patch("hummingbot.smart_components.executors.position_executor.position_executor.PositionExecutor.get_price", return_value=Decimal("101"))
    def test_to_format_status_is_closed(self, _):
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.open_order.order_id = "OID-BUY-1"
        position_executor.open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.open_order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor.open_order.order.update_with_trade_update(
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
        position_executor.executor_status = PositionExecutorStatus.COMPLETED
        type(position_executor).close_price = PropertyMock(return_value=Decimal(101))
        status = position_executor.to_format_status()
        self.assertIn("Trading Pair: ETH-USDT", status[0])
        self.assertIn("PNL (%): 0.80%", status[0])
        position_executor.stop()

    def test_process_order_canceled_event(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.open_order.order_id = "OID-BUY-1"
        event = OrderCancelledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
        )
        market = MagicMock()
        position_executor.process_order_canceled_event("102", market, event)
        self.assertEqual(position_executor.executor_status, PositionExecutorStatus.COMPLETED)
        self.assertEqual(position_executor.close_type, CloseType.EXPIRED)
        position_executor.stop()

    def test_trailing_stop_condition(self):
        position_config = self.get_position_config_trailing_stop()
        position_executor = PositionExecutor(self.strategy, position_config)
        position_executor.executor_status = PositionExecutorStatus.ACTIVE_POSITION
        type(position_executor).close_price = PropertyMock(side_effect=[Decimal("101"), Decimal("102"), Decimal("103"), Decimal("101")])

        # First: not activated
        self.assertEqual(position_executor.trailing_stop_condition(), False)
        self.assertEqual(position_executor._trailing_stop_activated, False)

        # Second: activated but not triggered
        self.assertEqual(position_executor.trailing_stop_condition(), False)
        self.assertEqual(position_executor._trailing_stop_activated, True)
        self.assertEqual(position_executor._trailing_stop_price, Decimal("102"))

        # Third: activated and updated
        self.assertEqual(position_executor.trailing_stop_condition(), False)
        self.assertEqual(position_executor._trailing_stop_activated, True)
        self.assertEqual(position_executor._trailing_stop_price, Decimal("102"))

        # Forth: triggered
        self.assertEqual(position_executor.trailing_stop_condition(), True)
        position_executor.stop()
