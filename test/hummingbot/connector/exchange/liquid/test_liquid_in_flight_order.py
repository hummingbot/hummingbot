from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.liquid.liquid_in_flight_order import LiquidInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType


class LiquidInFlightOrderTests(TestCase):

    def setUp(self):
        super().setUp()
        self.base_token = "BTC"
        self.quote_token = "USDT"
        self.trading_pair = f"{self.base_token}-{self.quote_token}"

    def _trade_info(self, trade_id, amount, price, fee, status="live"):
        return {
            "average_price": 10000.0,
            "client_order_id": "OID1",
            "created_at": 1639429916,
            "crypto_account_id": None,
            "currency_pair_code": "BTCUSDT",
            "disc_quantity": 0.0,
            "filled_quantity": amount,
            "funding_currency": "USDT",
            "iceberg_total_quantity": 0.0,
            "id": 5821066005,
            "leverage_level": 1,
            "margin_interest": 0.0,
            "margin_type": None,
            "margin_used": 0.0,
            "order_fee": fee,
            "order_type": "limit",
            "price": price,
            "product_code": "CASH",
            "product_id": 761,
            "quantity": 1.0,
            "side": "buy",
            "source_action": "manual",
            "source_exchange": 0,
            "status": status,
            "stop_loss": None,
            "take_profit": None,
            "target": "spot",
            "trade_id": None,
            "trading_type": "spot",
            "unwound_trade_id": None,
            "unwound_trade_leverage_level": None,
            "updated_at": trade_id
        }

    def test_creation_from_json(self):
        order_info = {
            "client_order_id": "OID1",
            "exchange_order_id": "EOID1",
            "trading_pair": self.trading_pair,
            "order_type": OrderType.LIMIT.name,
            "trade_type": TradeType.BUY.name,
            "price": "1000",
            "amount": "1",
            "executed_amount_base": "0.5",
            "executed_amount_quote": "500",
            "fee_asset": "USDT",
            "fee_paid": "5",
            "last_state": "closed",
        }

        order = LiquidInFlightOrder.from_json(order_info)

        self.assertEqual(order_info["client_order_id"], order.client_order_id)
        self.assertEqual(order_info["exchange_order_id"], order.exchange_order_id)
        self.assertEqual(order_info["trading_pair"], order.trading_pair)
        self.assertEqual(OrderType.LIMIT, order.order_type)
        self.assertEqual(TradeType.BUY, order.trade_type)
        self.assertEqual(Decimal(order_info["price"]), order.price)
        self.assertEqual(Decimal(order_info["amount"]), order.amount)
        self.assertEqual(order_info["last_state"], order.last_state)
        self.assertEqual(Decimal(order_info["executed_amount_base"]), order.executed_amount_base)
        self.assertEqual(Decimal(order_info["executed_amount_quote"]), order.executed_amount_quote)
        self.assertEqual(Decimal(order_info["fee_paid"]), order.fee_paid)
        self.assertEqual(order_info["fee_asset"], order.fee_asset)
        self.assertEqual(order_info, order.to_json())

    def test_update_with_partial_trade_event(self):
        order = LiquidInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = self._trade_info(1, 0.1, 10050.0, 10.0)

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("live", order.last_state)
        self.assertEqual(Decimal("0.1"), order.executed_amount_base)
        expected_executed_quote_amount = Decimal("0.1") * Decimal(
            str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["order_fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["funding_currency"], order.fee_asset)

    def test_update_with_full_fill_trade_event(self):
        order = LiquidInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = self._trade_info(1, 0.1, 10050.0, 10.0)

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("live", order.last_state)
        self.assertEqual(Decimal("0.1"), order.executed_amount_base)
        expected_executed_quote_amount = Decimal("0.1") * Decimal(str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["order_fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["funding_currency"], order.fee_asset)

        complete_event_info = self._trade_info(2, 1, 10060.0, 50.0)

        update_result = order.update_with_trade_update(complete_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("live", order.last_state)
        self.assertEqual(order.amount, order.executed_amount_base)
        expected_executed_quote_amount += Decimal("0.9") * Decimal(str(complete_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        # According to Liquid support team they inform fee in a cumulative way
        self.assertEqual(Decimal(complete_event_info["order_fee"]),
                         order.fee_paid)
        self.assertEqual(trade_event_info["funding_currency"], order.fee_asset)

    def test_update_with_repeated_trade_id_is_ignored(self):
        order = LiquidInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = self._trade_info(1, 0.1, 10050.0, 10.0)

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("live", order.last_state)
        self.assertEqual(Decimal("0.1"), order.executed_amount_base)
        expected_executed_quote_amount = Decimal("0.1") * Decimal(str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["order_fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["funding_currency"], order.fee_asset)

        complete_event_info = self._trade_info(1, 1, 10060.0, 50.0)

        update_result = order.update_with_trade_update(complete_event_info)

        self.assertFalse(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("live", order.last_state)
        self.assertEqual(Decimal("0.1"), order.executed_amount_base)
        expected_executed_quote_amount = Decimal("0.1") * Decimal(str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["order_fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["funding_currency"], order.fee_asset)

    def test_update_with_same_or_less_total_filled_amount_is_ignored(self):
        order = LiquidInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = self._trade_info(1, 0.1, 10050.0, 10.0)

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("live", order.last_state)
        self.assertEqual(Decimal("0.1"), order.executed_amount_base)
        expected_executed_quote_amount = Decimal("0.1") * Decimal(str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["order_fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["funding_currency"], order.fee_asset)

        new_event_info = self._trade_info(2, 0.09, 10060.0, 50.0)

        update_result = order.update_with_trade_update(new_event_info)

        self.assertFalse(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("live", order.last_state)
        self.assertEqual(Decimal("0.1"), order.executed_amount_base)
        expected_executed_quote_amount = Decimal("0.1") * Decimal(str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["order_fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["funding_currency"], order.fee_asset)

        new_event_info = self._trade_info(3, 0.1, 10060.0, 50.0)

        update_result = order.update_with_trade_update(new_event_info)

        self.assertFalse(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("live", order.last_state)
        self.assertEqual(Decimal("0.1"), order.executed_amount_base)
        expected_executed_quote_amount = Decimal("0.1") * Decimal(str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["order_fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["funding_currency"], order.fee_asset)
