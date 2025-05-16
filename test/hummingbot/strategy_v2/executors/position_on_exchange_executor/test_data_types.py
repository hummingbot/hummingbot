import unittest
from decimal import Decimal
from typing import Optional

from pydantic import ValidationError

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.strategy_v2.executors.position_executor.data_types import TrailingStop, TripleBarrierConfig
from hummingbot.strategy_v2.executors.position_on_exchange_executor.data_types import PositionOnExchangeExecutorConfig


class PositionOnExchangeExecutorConfigTest(unittest.TestCase):

    def test_valid_config(self):
        config = PositionOnExchangeExecutorConfig(
            timestamp=123,
            connector_name="binance",
            trading_pair="BTC-USDT",
            side=TradeType.BUY,
            amount=Decimal("1"),
            entry_price=Decimal("10000"),
            triple_barrier_config=TripleBarrierConfig(),
        )

        self.assertEqual(config.type, "position_on_exchange_executor")
        self.assertEqual(config.timestamp, 123)
        self.assertEqual(config.connector_name, "binance")
        self.assertEqual(config.trading_pair, "BTC-USDT")
        self.assertEqual(config.side, TradeType.BUY)
        self.assertEqual(config.amount, Decimal("1"))
        self.assertEqual(config.entry_price, Decimal("10000"))
        self.assertIsInstance(config.triple_barrier_config, TripleBarrierConfig)

    def test_missing_required_fields(self):
        with self.assertRaises(ValidationError):
            PositionOnExchangeExecutorConfig()  # Missing all required fields

    def test_invalid_timestamp(self):
        with self.assertRaises(ValidationError):
            PositionOnExchangeExecutorConfig(
                timestamp="invalid",  # Invalid timestamp type
                connector_name="binance",
                trading_pair="BTC-USDT",
                side=TradeType.BUY,
                amount=Decimal("1"),
                entry_price=Decimal("10000"),
                triple_barrier_config=TripleBarrierConfig(),
            )

    def test_invalid_side(self):
        with self.assertRaises(ValidationError):
            PositionOnExchangeExecutorConfig(
                timestamp=123,
                connector_name="binance",
                trading_pair="BTC-USDT",
                side="invalid",  # Invalid side type
                amount=Decimal("1"),
                entry_price=Decimal("10000"),
                triple_barrier_config=TripleBarrierConfig(),
            )

    def test_invalid_amount(self):
        with self.assertRaises(ValidationError):
            PositionOnExchangeExecutorConfig(
                timestamp=123,
                connector_name="binance",
                trading_pair="BTC-USDT",
                side=TradeType.BUY,
                amount="invalid",  # Invalid amount type
                entry_price=Decimal("10000"),
                triple_barrier_config=TripleBarrierConfig(),
            )

    def test_invalid_entry_price(self):
        with self.assertRaises(ValidationError):
            PositionOnExchangeExecutorConfig(
                timestamp=123,
                connector_name="binance",
                trading_pair="BTC-USDT",
                side=TradeType.BUY,
                amount=Decimal("1"),
                entry_price="invalid",  # Invalid entry_price type
                triple_barrier_config=TripleBarrierConfig(),
            )

    def test_optional_fields_none(self):
        config = PositionOnExchangeExecutorConfig(
            timestamp=123,
            connector_name="binance",
            trading_pair="BTC-USDT",
            side=TradeType.BUY,
            amount=Decimal("1"),
            entry_price=Decimal("10000"),
        )

        self.assertIsNone(config.triple_barrier_config.stop_loss)
        self.assertIsNone(config.triple_barrier_config.take_profit)
        self.assertEqual(config.triple_barrier_config.stop_loss_order_type, OrderType.STOP_LOSS)

    @staticmethod
    def create_config_with_triple_barrier(
            stop_loss: Optional[Decimal] = None,
            take_profit: Optional[Decimal] = None,
            stop_loss_order_type: Optional[OrderType] = OrderType.MARKET,
            trailing_stop: Optional[TrailingStop] = None,
    ):
        return PositionOnExchangeExecutorConfig(
            timestamp=123,
            connector_name="binance",
            trading_pair="BTC-USDT",
            side=TradeType.BUY,
            amount=Decimal("1"),
            entry_price=Decimal("10000"),
            triple_barrier_config=TripleBarrierConfig(
                stop_loss=stop_loss,
                take_profit=take_profit,
                stop_loss_order_type=stop_loss_order_type,
                trailing_stop=trailing_stop,
            ),
        )

    def test_triple_barrier_config_valid(self):
        config = self.create_config_with_triple_barrier(
            stop_loss=Decimal("0.05"),
            take_profit=Decimal("0.1"),
            stop_loss_order_type=OrderType.LIMIT,
            trailing_stop=TrailingStop(activation_price=Decimal('11000'), trailing_delta=Decimal('0.05'))
        )

        self.assertEqual(config.triple_barrier_config.stop_loss, Decimal("0.05"))
        self.assertEqual(config.triple_barrier_config.take_profit, Decimal("0.1"))
        self.assertEqual(config.triple_barrier_config.stop_loss_order_type, OrderType.LIMIT)
        self.assertEqual(config.triple_barrier_config.trailing_stop.activation_price, Decimal('11000'))
        self.assertEqual(config.triple_barrier_config.trailing_stop.trailing_delta, Decimal('0.05'))

    def test_triple_barrier_config_invalid_stop_loss(self):
        with self.assertRaises(ValidationError):
            self.create_config_with_triple_barrier(stop_loss="invalid")

    def test_triple_barrier_config_invalid_take_profit(self):
        with self.assertRaises(ValidationError):
            self.create_config_with_triple_barrier(take_profit="invalid")

    def test_triple_barrier_config_invalid_stop_loss_order_type(self):
        with self.assertRaises(ValidationError):
            self.create_config_with_triple_barrier(stop_loss_order_type="invalid")
