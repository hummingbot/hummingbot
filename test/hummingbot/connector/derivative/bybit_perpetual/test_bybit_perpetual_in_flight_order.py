from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_in_flight_order import BybitPerpetualInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType, PositionAction


class BybitPerpetualInFlightOrderTests(TestCase):

    def _example_json(self):
        return {"client_order_id": "C1",
                "exchange_order_id": "X1",
                "trading_pair": "BTC-USDT",
                "order_type": "LIMIT",
                "trade_type": "BUY",
                "price": "35000",
                "amount": "1.1",
                "last_state": "Created",
                "executed_amount_base": "0.5",
                "executed_amount_quote": "15000",
                "fee_asset": "BTC",
                "fee_paid": "0",
                "leverage": "10",
                "position": "OPEN"}

    def test_instance_creation(self):
        order = BybitPerpetualInFlightOrder(client_order_id="C1",
                                            exchange_order_id="X1",
                                            trading_pair="BTC-USDT",
                                            order_type=OrderType.LIMIT,
                                            trade_type=TradeType.SELL,
                                            price=Decimal("35000"),
                                            amount=Decimal("1.1"),
                                            leverage=10,
                                            position=PositionAction.OPEN.name)

        self.assertEqual("C1", order.client_order_id)
        self.assertEqual("X1", order.exchange_order_id)
        self.assertEqual("BTC-USDT", order.trading_pair)
        self.assertEqual(OrderType.LIMIT, order.order_type)
        self.assertEqual(TradeType.SELL, order.trade_type)
        self.assertEqual(Decimal("35000"), order.price)
        self.assertEqual(Decimal("1.1"), order.amount)
        self.assertEqual(Decimal("0"), order.executed_amount_base)
        self.assertEqual(Decimal("0"), order.executed_amount_quote)
        self.assertEqual(order.quote_asset, order.fee_asset)
        self.assertEqual(Decimal("0"), order.fee_paid)
        self.assertEqual("Created", order.last_state)
        self.assertEqual(10, order.leverage)
        self.assertEqual(PositionAction.OPEN.name, order.position)

    def test_fee_asset_is_base_asset_for_non_usdt_quote(self):
        order = BybitPerpetualInFlightOrder(client_order_id="C1",
                                            exchange_order_id="X1",
                                            trading_pair="BTC-USD",
                                            order_type=OrderType.LIMIT,
                                            trade_type=TradeType.SELL,
                                            price=Decimal("35000"),
                                            amount=Decimal("1.1"),
                                            leverage=10,
                                            position=PositionAction.OPEN.name)

        self.assertEqual(order.base_asset, order.fee_asset)

    def test_create_from_json(self):
        order = BybitPerpetualInFlightOrder.from_json(self._example_json())

        self.assertEqual("C1", order.client_order_id)
        self.assertEqual("X1", order.exchange_order_id)
        self.assertEqual("BTC-USDT", order.trading_pair)
        self.assertEqual(OrderType.LIMIT, order.order_type)
        self.assertEqual(TradeType.BUY, order.trade_type)
        self.assertEqual(Decimal("35000"), order.price)
        self.assertEqual(Decimal("1.1"), order.amount)
        self.assertEqual(Decimal("0.5"), order.executed_amount_base)
        self.assertEqual(Decimal("15000"), order.executed_amount_quote)
        self.assertEqual(order.base_asset, order.fee_asset)
        self.assertEqual(Decimal("0"), order.fee_paid)
        self.assertEqual("Created", order.last_state)
        self.assertEqual(10, order.leverage)
        self.assertEqual(PositionAction.OPEN.name, order.position)

    def test_is_done(self):
        order = BybitPerpetualInFlightOrder.from_json(self._example_json())

        self.assertFalse(order.is_done)

        for status in ["Filled", "Canceled", "Rejected"]:
            order.last_state = status
            self.assertTrue(order.is_done)

    def test_is_failure(self):
        order = BybitPerpetualInFlightOrder.from_json(self._example_json())

        for status in ["Created", "New", "PartiallyFilled", "Filled", "Cancelled", "PendingCancel"]:
            order.last_state = status
            self.assertFalse(order.is_failure)

        order.last_state = "Rejected"
        self.assertTrue(order.is_failure)

    def test_is_cancelled(self):
        order = BybitPerpetualInFlightOrder.from_json(self._example_json())

        for status in ["Created", "New", "PartiallyFilled", "Filled", "Rejected", "PendingCancel"]:
            order.last_state = status
            self.assertFalse(order.is_cancelled)

        for status in ["Cancelled"]:
            order.last_state = status
            self.assertTrue(order.is_cancelled)

    def test_is_created(self):
        order = BybitPerpetualInFlightOrder.from_json(self._example_json())

        for status in ["New", "PartiallyFilled", "Filled", "Rejected", "PendingCancel", "Cancelled"]:
            order.last_state = status
            self.assertFalse(order.is_created)

        for status in ["Created"]:
            order.last_state = status
            self.assertTrue(order.is_created)

    def test_is_new(self):
        order = BybitPerpetualInFlightOrder.from_json(self._example_json())

        for status in ["Created", "PartiallyFilled", "Filled", "Rejected", "PendingCancel", "Cancelled"]:
            order.last_state = status
            self.assertFalse(order.is_new)

        for status in ["New"]:
            order.last_state = status
            self.assertTrue(order.is_new)

    def test_mark_as_filled(self):
        order = BybitPerpetualInFlightOrder.from_json(self._example_json())

        order.mark_as_filled()
        self.assertEqual("Filled", order.last_state)

    def test_to_json(self):
        order = BybitPerpetualInFlightOrder.from_json(self._example_json())

        self.assertEqual(self._example_json(), order.to_json())

    def test_update_with_trade_update(self):
        order = BybitPerpetualInFlightOrder.from_json(self._example_json())

        trade_update_for_different_order_id = {
            "symbol": "BTCUSDT",
            "side": "Buy",
            "order_id": "X5",
            "exec_id": "T5",
            "order_link_id": "C5",
            "price": "8300",
            "order_qty": 0.01,
            "exec_type": "Trade",
            "exec_qty": 0.01,
            "exec_fee": "0.00000009",
            "leaves_qty": 0,
            "is_maker": False,
            "trade_time": "2020-01-14T14:07:23.629Z"
        }

        update_result = order.update_with_trade_update(trade_update_for_different_order_id)
        self.assertFalse(update_result)

        valid_trade_update = {
            "symbol": "BTCUSDT",
            "side": "Buy",
            "order_id": "X1",
            "exec_id": "T1",
            "order_link_id": "C1",
            "price": "44000",
            "order_qty": 0.1,
            "exec_type": "Trade",
            "exec_qty": 0.1,
            "exec_fee": "330",
            "leaves_qty": 0,
            "is_maker": False,
            "trade_time": "2020-01-14T14:07:23.629Z"
        }

        update_result = order.update_with_trade_update(valid_trade_update)
        self.assertTrue(update_result)
        self.assertEqual(Decimal("0.1") + Decimal(self._example_json()["executed_amount_base"]),
                         order.executed_amount_base)
        self.assertEqual(Decimal("4400") + Decimal(self._example_json()["executed_amount_quote"]),
                         order.executed_amount_quote)
        self.assertEqual(Decimal("330") + Decimal(self._example_json()["fee_paid"]),
                         order.fee_paid)

        repeated_trade_update = valid_trade_update
        update_result = order.update_with_trade_update(repeated_trade_update)
        self.assertFalse(update_result)

    def test_update_with_trade_update_using_rest_endpoint_format(self):
        order = BybitPerpetualInFlightOrder.from_json(self._example_json())

        valid_trade_update = {
            "closed_size": 0,
            "cross_seq": 277136382,
            "exec_fee": "330",
            "exec_id": "T1",
            "exec_price": "44000",
            "exec_qty": 0.1,
            "exec_time": "1571676941.70682",
            "exec_type": "Trade",
            "exec_value": "4400",
            "fee_rate": "0.00075",
            "last_liquidity_ind": "RemovedLiquidity",
            "leaves_qty": 0,
            "nth_fill": 2,
            "order_id": "X1",
            "order_link_id": "C1",
            "order_price": "44000",
            "order_qty": 0.1,
            "order_type": "Limit",
            "side": "Buy",
            "symbol": "BTCUSDT",
            "user_id": 1,
            "trade_time_ms": 1577480599000

        }

        update_result = order.update_with_trade_update(valid_trade_update)
        self.assertTrue(update_result)
        self.assertEqual(Decimal("0.1") + Decimal(self._example_json()["executed_amount_base"]),
                         order.executed_amount_base)
        self.assertEqual(Decimal("4400") + Decimal(self._example_json()["executed_amount_quote"]),
                         order.executed_amount_quote)
        self.assertEqual(Decimal("330") + Decimal(self._example_json()["fee_paid"]),
                         order.fee_paid)

        repeated_trade_update = valid_trade_update
        update_result = order.update_with_trade_update(repeated_trade_update)
        self.assertFalse(update_result)

    def test_update_with_trade_update_quote_amount_for_non_usdt_orders(self):
        order = BybitPerpetualInFlightOrder(client_order_id="C1",
                                            exchange_order_id="X1",
                                            trading_pair="BTC-USD",
                                            order_type=OrderType.LIMIT,
                                            trade_type=TradeType.SELL,
                                            price=Decimal("35000"),
                                            amount=Decimal("1.1"),
                                            leverage=10,
                                            position=PositionAction.OPEN.name)

        valid_trade_update = {
            "symbol": "BTCUSD",
            "side": "Buy",
            "order_id": "X1",
            "exec_id": "T1",
            "order_link_id": "C1",
            "price": "8000",
            "order_qty": 10000,
            "exec_type": "Trade",
            "exec_qty": 10000,
            "exec_fee": "0.09375",
            "leaves_qty": 0,
            "is_maker": False,
            "trade_time": "2020-01-14T14:07:23.629Z"
        }

        update_result = order.update_with_trade_update(valid_trade_update)
        self.assertTrue(update_result)
        self.assertEqual(Decimal("10000"), order.executed_amount_base)
        self.assertEqual(Decimal("1.25"), order.executed_amount_quote)
        self.assertEqual(Decimal("0.09375"), order.fee_paid)
