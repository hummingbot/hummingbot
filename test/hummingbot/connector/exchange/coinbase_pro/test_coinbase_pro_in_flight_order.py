from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_in_flight_order import CoinbaseProInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType


class CoinbaseProInFlightOrderTests(TestCase):

    def setUp(self):
        super().setUp()
        self.base_token = "BTC"
        self.quote_token = "USDT"
        self.trading_pair = f"{self.base_token}-{self.quote_token}"

    def test_update_with_partial_trade_event(self):
        order = CoinbaseProInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = {
            "type": "match",
            "trade_id": 1,
            "sequence": 50,
            "maker_order_id": "EOID1",
            "taker_order_id": "132fb6ae-456b-4654-b4e0-d681ac05cea1",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": "BTC-USDT",
            "size": "0.1",
            "price": "10050.0",
            "side": "buy",
            "taker_user_id": "5844eceecf7e803e259d0365",
            "user_id": "5844eceecf7e803e259d0365",
            "taker_profile_id": "765d1549-9660-4be2-97d4-fa2d65fa3352",
            "profile_id": "765d1549-9660-4be2-97d4-fa2d65fa3352",
            "taker_fee_rate": "0.005"
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("open", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["size"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["size"])) * Decimal(str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["taker_fee_rate"]) * expected_executed_quote_amount, order.fee_paid)
        self.assertEqual(order.quote_asset, order.fee_asset)

    def test_update_with_full_fill_trade_event(self):
        order = CoinbaseProInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = {
            "type": "match",
            "trade_id": 1,
            "sequence": 50,
            "maker_order_id": "EOID1",
            "taker_order_id": "132fb6ae-456b-4654-b4e0-d681ac05cea1",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": "BTC-USDT",
            "size": "0.1",
            "price": "10050.0",
            "side": "buy",
            "taker_user_id": "5844eceecf7e803e259d0365",
            "user_id": "5844eceecf7e803e259d0365",
            "taker_profile_id": "765d1549-9660-4be2-97d4-fa2d65fa3352",
            "profile_id": "765d1549-9660-4be2-97d4-fa2d65fa3352",
            "taker_fee_rate": "0.005"
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("open", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["size"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["size"])) * Decimal(
            str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        expected_partial_event_fee = (Decimal(trade_event_info["taker_fee_rate"]) *
                                      expected_executed_quote_amount)
        self.assertEqual(expected_partial_event_fee, order.fee_paid)

        complete_event_info = {
            "type": "match",
            "trade_id": 2,
            "sequence": 50,
            "maker_order_id": "EOID1",
            "taker_order_id": "132fb6ae-456b-4654-b4e0-d681ac05cea1",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": "BTC-USDT",
            "size": "0.9",
            "price": "10050.0",
            "side": "buy",
            "taker_user_id": "5844eceecf7e803e259d0365",
            "user_id": "5844eceecf7e803e259d0365",
            "taker_profile_id": "765d1549-9660-4be2-97d4-fa2d65fa3352",
            "profile_id": "765d1549-9660-4be2-97d4-fa2d65fa3352",
            "taker_fee_rate": "0.001"
        }

        update_result = order.update_with_trade_update(complete_event_info)

        self.assertTrue(update_result)
        # orders are marked as done with the done event
        self.assertFalse(order.is_done)
        self.assertEqual("open", order.last_state)
        self.assertEqual(order.amount, order.executed_amount_base)
        expected_executed_quote_amount += Decimal(str(complete_event_info["size"])) * Decimal(
            str(complete_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        expected_complete_event_fee = (Decimal(complete_event_info["taker_fee_rate"]) *
                                       Decimal(str(complete_event_info["size"])) *
                                       Decimal(str(complete_event_info["price"])))
        self.assertEqual(expected_partial_event_fee + expected_complete_event_fee, order.fee_paid)

    def test_update_with_repeated_trade_id_is_ignored(self):
        order = CoinbaseProInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = {
            "type": "match",
            "trade_id": 1,
            "sequence": 50,
            "maker_order_id": "EOID1",
            "taker_order_id": "132fb6ae-456b-4654-b4e0-d681ac05cea1",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": "BTC-USDT",
            "size": "0.1",
            "price": "10050.0",
            "side": "buy",
            "taker_user_id": "5844eceecf7e803e259d0365",
            "user_id": "5844eceecf7e803e259d0365",
            "taker_profile_id": "765d1549-9660-4be2-97d4-fa2d65fa3352",
            "profile_id": "765d1549-9660-4be2-97d4-fa2d65fa3352",
            "taker_fee_rate": "0.005"
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)

        complete_event_info = {
            "type": "match",
            "trade_id": 1,
            "sequence": 50,
            "maker_order_id": "EOID1",
            "taker_order_id": "132fb6ae-456b-4654-b4e0-d681ac05cea1",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": "BTC-USDT",
            "size": "0.9",
            "price": "10050.0",
            "side": "buy",
            "taker_user_id": "5844eceecf7e803e259d0365",
            "user_id": "5844eceecf7e803e259d0365",
            "taker_profile_id": "765d1549-9660-4be2-97d4-fa2d65fa3352",
            "profile_id": "765d1549-9660-4be2-97d4-fa2d65fa3352",
            "taker_fee_rate": "0.001"
        }

        update_result = order.update_with_trade_update(complete_event_info)

        self.assertFalse(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("open", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["size"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["size"])) * Decimal(
            str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["taker_fee_rate"]) * expected_executed_quote_amount, order.fee_paid)
