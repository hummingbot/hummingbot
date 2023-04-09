import unittest
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock

from hummingbot.core.data_type.common import OrderType, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.event.events import BuyOrderCompletedEvent, OrderFilledEvent
from hummingbot.smart_components.position_executor.data_types import (
    PositionConfig,
    PositionExecutorStatus,
    TrackedOrder,
)
from hummingbot.smart_components.position_executor.position_executor import PositionExecutor


class TestPositionExecutor(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.strategy = self.create_mock_strategy()

    def create_mock_strategy(self):
        market = MagicMock()
        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock()
        type(strategy).market_info = PropertyMock(return_value=market_info)
        type(strategy).trading_pair = PropertyMock(return_value="ETH-USDT")
        strategy.buy.side_effect = ["OID-BUY-1", "OID-BUY-2", "OID-BUY-3"]
        strategy.sell.side_effect = ["OID-SELL-1", "OID-SELL-2", "OID-SELL-3"]
        strategy.cancel.return_value = None
        return strategy

    def get_position_config_market_long(self):
        return PositionConfig(timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                              order_type=OrderType.MARKET,
                              side=PositionSide.LONG, entry_price=Decimal("100"), amount=Decimal("1"),
                              stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60)

    def get_position_config_market_short(self):
        return PositionConfig(timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                              order_type=OrderType.MARKET,
                              side=PositionSide.SHORT, entry_price=Decimal("100"), amount=Decimal("1"),
                              stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60)

    def test_init(self):
        position_config = PositionConfig(timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                                         order_type=OrderType.MARKET,
                                         side=PositionSide.LONG, entry_price=Decimal("100"), amount=Decimal("1"),
                                         stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60)
        position_executor = PositionExecutor(position_config, self.strategy)
        self.assertIsInstance(position_executor._position_config, PositionConfig)
        self.assertEqual(position_executor._position_config, position_config)
        self.assertEqual(position_executor._strategy, self.strategy)
        self.assertEqual(position_executor._status, PositionExecutorStatus.NOT_STARTED)
        self.assertIsInstance(position_executor._open_order, TrackedOrder)
        self.assertIsInstance(position_executor._take_profit_order, TrackedOrder)
        self.assertIsInstance(position_executor._time_limit_order, TrackedOrder)
        self.assertIsInstance(position_executor._stop_loss_order, TrackedOrder)
        self.assertIsNone(position_executor._close_timestamp)

    def test_status(self):
        position_config = self.get_position_config_market_short()
        position_executor = PositionExecutor(position_config, self.strategy)
        assert position_executor.status == PositionExecutorStatus.NOT_STARTED
        position_executor.status = PositionExecutorStatus.ORDER_PLACED
        assert position_executor.status == PositionExecutorStatus.ORDER_PLACED

    def test_is_closed(self):
        position_config = self.get_position_config_market_short()
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.status = PositionExecutorStatus.CLOSED_BY_TIME_LIMIT
        self.assertTrue(position_executor.is_closed)

    def test_control_position_not_started_create_open_order(self):
        position_config = self.get_position_config_market_short()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.control_position()
        self.assertEqual(position_executor.open_order.order_id, "OID-SELL-1")

    def test_control_position_not_started_expired(self):
        position_config = self.get_position_config_market_short()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234569890)
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.control_position()
        self.assertIsNone(position_executor.open_order.order_id)
        self.assertEqual(position_executor.status, PositionExecutorStatus.CANCELED_BY_TIME_LIMIT)

    def test_control_position_order_placed_cancel_open_order(self):
        position_config = self.get_position_config_market_short()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234569890)
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.open_order.order_id = "OID-SELL-1"
        position_executor.status = PositionExecutorStatus.ORDER_PLACED
        position_executor.control_position()
        position_executor._strategy.cancel.assert_called_with(
            connector_name="binance",
            trading_pair="ETH-USDT",
            order_id="OID-SELL-1")

    def test_control_position_order_placed_not_cancel_open_order(self):
        position_config = self.get_position_config_market_short()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.open_order.order_id = "OID-SELL-1"
        position_executor.status = PositionExecutorStatus.ORDER_PLACED
        position_executor.control_position()
        position_executor._strategy.cancel.assert_not_called()

    def test_control_position_active_position_create_take_profit(self):
        position_config = self.get_position_config_market_short()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        self.strategy.connectors[position_config.exchange].get_mid_price.return_value = Decimal(100)
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.open_order.order_id = "OID-SELL-1"
        position_executor.open_order.order = InFlightOrder(
            client_order_id="OID-SELL-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.order_type,
            trade_type=TradeType.SELL,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor.open_order.order.executed_amount_base = position_config.amount
        position_executor.open_order.order.order_fills = {
            "1": TradeUpdate(
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
        }

        position_executor.status = PositionExecutorStatus.ACTIVE_POSITION
        position_executor.control_position()
        self.assertEqual(position_executor.take_profit_order.order_id, "OID-BUY-1")

    def test_control_position_active_position_close_by_stop_loss(self):
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        self.strategy.connectors[position_config.exchange].get_mid_price.return_value = Decimal(70)
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.open_order.order_id = "OID-BUY-1"
        position_executor.open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor.open_order.order.executed_amount_base = position_config.amount
        position_executor.open_order.order.order_fills = {
            "1": TradeUpdate(
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
        }
        position_executor.status = PositionExecutorStatus.ACTIVE_POSITION
        position_executor.control_position()
        self.assertEqual(position_executor.stop_loss_order.order_id, "OID-SELL-2")
        self.assertEqual(position_executor.status, PositionExecutorStatus.CLOSE_PLACED)

    def test_control_position_active_position_close_by_time_limit(self):
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234597890)
        self.strategy.connectors[position_config.exchange].get_mid_price.return_value = Decimal(100)
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.open_order.order_id = "OID-BUY-1"
        position_executor.open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor.open_order.order.executed_amount_base = position_config.amount
        position_executor.open_order.order.order_fills = {
            "1": TradeUpdate(
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
        }
        position_executor.status = PositionExecutorStatus.ACTIVE_POSITION
        position_executor.control_position()
        self.assertEqual(position_executor.time_limit_order.order_id, "OID-SELL-2")
        self.assertEqual(position_executor.status, PositionExecutorStatus.CLOSE_PLACED)

    def test_clean_executor(self):
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234597890)
        self.strategy.connectors[position_config.exchange].get_mid_price.return_value = Decimal(100)
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.take_profit_order.order_id = "OID-SELL-1"
        position_executor.take_profit_order.order = InFlightOrder(
            client_order_id="OID-SELL-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.order_type,
            trade_type=TradeType.SELL,
            amount=position_config.amount,
            price=position_executor.take_profit_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN
        )
        position_executor.status = PositionExecutorStatus.CLOSED_BY_TIME_LIMIT
        position_executor.control_position()
        position_executor._strategy.cancel.assert_called_with(
            connector_name="binance",
            trading_pair="ETH-USDT",
            order_id="OID-SELL-1")

    def test_pnl(self):
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        self.strategy.connectors[position_config.exchange].get_mid_price.return_value = Decimal(101)
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.open_order.order_id = "OID-BUY-1"
        position_executor.open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor.open_order.order.executed_amount_base = position_config.amount
        position_executor.open_order.order.order_fills = {
            "1": TradeUpdate(
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
        }

        position_executor.status = PositionExecutorStatus.ACTIVE_POSITION
        position_executor.control_position()
        self.assertEqual(position_executor.take_profit_order.order_id, "OID-SELL-1")
        self.assertEqual(position_executor.pnl, Decimal("0.01"))

    def test_control_position_close_placed_stop_loss_failed(self):
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        self.strategy.connectors[position_config.exchange].get_mid_price.return_value = Decimal(70)
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.open_order.order_id = "OID-BUY-1"
        position_executor.open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor.open_order.order.executed_amount_base = position_config.amount
        position_executor.open_order.order.order_fills = {
            "1": TradeUpdate(
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
        }
        position_executor.stop_loss_order.order_id = "OID-SELL-MOCKED"
        position_executor.stop_loss_order.order = InFlightOrder(
            client_order_id="OID-SELL-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.order_type,
            trade_type=TradeType.SELL,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FAILED
        )
        position_executor.status = PositionExecutorStatus.CLOSE_PLACED
        position_executor.control_position()
        self.assertEqual(position_executor.stop_loss_order.order_id, "OID-SELL-1")
        self.assertEqual(position_executor.status, PositionExecutorStatus.CLOSE_PLACED)

    def test_control_position_close_placed_time_limit_failed(self):
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        self.strategy.connectors[position_config.exchange].get_mid_price.return_value = Decimal(70)
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.open_order.order_id = "OID-BUY-1"
        position_executor.open_order.order = InFlightOrder(
            client_order_id="OID-BUY-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.order_type,
            trade_type=TradeType.BUY,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        position_executor.open_order.order.executed_amount_base = position_config.amount
        position_executor.open_order.order.order_fills = {
            "1": TradeUpdate(
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
        }
        position_executor.time_limit_order.order_id = "OID-SELL-MOCKED"
        position_executor.time_limit_order.order = InFlightOrder(
            client_order_id="OID-SELL-1",
            exchange_order_id="EOID4",
            trading_pair=position_config.trading_pair,
            order_type=position_config.order_type,
            trade_type=TradeType.SELL,
            amount=position_config.amount,
            price=position_config.entry_price,
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FAILED
        )
        position_executor.status = PositionExecutorStatus.CLOSE_PLACED
        position_executor.control_position()
        self.assertEqual(position_executor.time_limit_order.order_id, "OID-SELL-1")
        self.assertEqual(position_executor.status, PositionExecutorStatus.CLOSE_PLACED)

    def test_process_order_completed_event_open_order(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.open_order.order_id = "OID-BUY-1"
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=position_config.amount,
            quote_asset_amount=position_config.amount * position_config.entry_price,
            order_type=position_config.order_type,
            exchange_order_id="ED140"
        )
        market = MagicMock()
        position_executor.process_order_completed_event("102", market, event)
        self.assertEqual(position_executor.status, PositionExecutorStatus.ACTIVE_POSITION)

    def test_process_order_completed_event_stop_loss_order(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.stop_loss_order.order_id = "OID-BUY-1"
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=position_config.amount,
            quote_asset_amount=position_config.amount * position_config.entry_price,
            order_type=position_config.order_type,
            exchange_order_id="ED140"
        )
        market = MagicMock()
        position_executor.process_order_completed_event("102", market, event)
        self.assertEqual(position_executor.close_timestamp, 1234567890)
        self.assertEqual(position_executor.status, PositionExecutorStatus.CLOSED_BY_STOP_LOSS)

    def test_process_order_completed_event_time_limit_order(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.time_limit_order.order_id = "OID-BUY-1"
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=position_config.amount,
            quote_asset_amount=position_config.amount * position_config.entry_price,
            order_type=position_config.order_type,
            exchange_order_id="ED140"
        )
        market = MagicMock()
        position_executor.process_order_completed_event("102", market, event)
        self.assertEqual(position_executor.close_timestamp, 1234567890)
        self.assertEqual(position_executor.status, PositionExecutorStatus.CLOSED_BY_TIME_LIMIT)

    def test_process_order_completed_event_take_profit_order(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.take_profit_order.order_id = "OID-BUY-1"
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=position_config.amount,
            quote_asset_amount=position_config.amount * position_config.entry_price,
            order_type=position_config.order_type,
            exchange_order_id="ED140"
        )
        market = MagicMock()
        position_executor.process_order_completed_event("102", market, event)
        self.assertEqual(position_executor.close_timestamp, 1234567890)
        self.assertEqual(position_executor.status, PositionExecutorStatus.CLOSED_BY_TAKE_PROFIT)

    def test_process_order_filled_event_open_order_not_started(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.open_order.order_id = "OID-BUY-1"
        event = OrderFilledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            trading_pair="ETH-USDT",
            price=position_config.entry_price,
            amount=position_config.amount,
            order_type=position_config.order_type,
            trade_type=TradeType.SELL,
            trade_fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))])
        )
        market = MagicMock()
        position_executor.process_order_filled_event("102", market, event)
        self.assertEqual(position_executor.status, PositionExecutorStatus.ACTIVE_POSITION)

    def test_process_order_filled_event_open_order_started(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.open_order.order_id = "OID-BUY-1"
        event = OrderFilledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            trading_pair="ETH-USDT",
            price=position_config.entry_price,
            amount=position_config.amount,
            order_type=position_config.order_type,
            trade_type=TradeType.SELL,
            trade_fee=AddedToCostTradeFee(flat_fees=[TokenAmount(token="USDT", amount=Decimal("0.2"))])
        )
        market = MagicMock()
        position_executor.status = PositionExecutorStatus.ACTIVE_POSITION
        position_executor.process_order_filled_event("102", market, event)
        self.assertEqual(position_executor.status, PositionExecutorStatus.ACTIVE_POSITION)

    def test_to_format_status(self):
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        self.strategy.connectors[position_config.exchange].get_mid_price.return_value = Decimal(101)
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.status = PositionExecutorStatus.ACTIVE_POSITION
        status = position_executor.to_format_status()
        self.assertIn("Trading Pair: ETH-USDT", status[0])
        self.assertIn("PNL: 1.00%", status[0])

    def test_to_format_status_is_closed(self):
        position_config = self.get_position_config_market_long()
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234567890)
        self.strategy.connectors[position_config.exchange].get_mid_price.return_value = Decimal(101)
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.status = PositionExecutorStatus.CLOSED_BY_TAKE_PROFIT
        type(position_executor).close_price = PropertyMock(return_value=Decimal(101))
        status = position_executor.to_format_status()
        self.assertIn("Trading Pair: ETH-USDT", status[0])
        self.assertIn("PNL: 1.00%", status[0])

    def test_close_order_is_none(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(position_config, self.strategy)
        self.assertIsNone(position_executor.close_order)

    def test_close_order_take_profit(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.status = PositionExecutorStatus.CLOSED_BY_TAKE_PROFIT
        position_executor.take_profit_order.order_id = "OID-SELL-1"
        self.assertEqual(position_executor.close_order.order_id, "OID-SELL-1")

    def test_close_order_stop_loss(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.status = PositionExecutorStatus.CLOSED_BY_STOP_LOSS
        position_executor.stop_loss_order.order_id = "OID-SELL-1"
        self.assertEqual(position_executor.close_order.order_id, "OID-SELL-1")

    def test_close_order_time_limit(self):
        position_config = self.get_position_config_market_long()
        position_executor = PositionExecutor(position_config, self.strategy)
        position_executor.status = PositionExecutorStatus.CLOSED_BY_TIME_LIMIT
        position_executor.time_limit_order.order_id = "OID-SELL-1"
        self.assertEqual(position_executor.close_order.order_id, "OID-SELL-1")
