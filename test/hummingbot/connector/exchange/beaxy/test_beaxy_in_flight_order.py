from datetime import datetime
from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.beaxy.beaxy_in_flight_order import BeaxyInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType


class BeaxyInFlightOrderTests(TestCase):

    def setUp(self):
        super().setUp()
        self.base_token = "BTC"
        self.quote_token = "USDT"
        self.trading_pair = f"{self.base_token}-{self.quote_token}"

    def test_update_with_partial_trade_event(self):
        order = BeaxyInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1),
            created_at=datetime.now()
        )

        trade_event_info = {
            "order_id": "EOID1",
            "symbol": "BTCUSDT",
            "wallet_id": "8576DAF5-E033-46C6-8EFD-385F8A4662F7",
            "comment": "HBOT-buy-ETH-USDT-1638969314002553",
            "time_in_force": "good_till_cancel",
            "order_type": "limit",
            "side": "buy",
            "order_status": "partially_filled",
            "size": "1.0",
            "trade_size": "0.1",
            "trade_price": "10050.0",
            "limit_price": "10000",
            "stop_price": "None",
            "filled_size": "0.1",
            "average_price": "10000.0",
            "open_time": "2021-12-08T13:15:14.779Z",
            "close_time": "2021-12-08T13:15:14.787Z",
            "commission": "10.0",
            "commission_currency": "USDT",
            "timestamp": "2021-12-08T13:15:14.785Z"
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("new", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["trade_size"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["trade_size"])) * Decimal(
            str(trade_event_info["trade_price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["commission"]), order.fee_paid)
        self.assertEqual(trade_event_info["commission_currency"], order.fee_asset)

    def test_update_with_full_fill_trade_event(self):
        order = BeaxyInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1),
            created_at=datetime.now()
        )

        trade_event_info = {
            "order_id": "EOID1",
            "symbol": "BTCUSDT",
            "wallet_id": "8576DAF5-E033-46C6-8EFD-385F8A4662F7",
            "comment": "HBOT-buy-ETH-USDT-1638969314002553",
            "time_in_force": "good_till_cancel",
            "order_type": "limit",
            "side": "buy",
            "order_status": "partially_filled",
            "size": "1.0",
            "trade_size": "0.1",
            "trade_price": "10050.0",
            "limit_price": "10000",
            "stop_price": "None",
            "filled_size": "0.1",
            "average_price": "10000.0",
            "open_time": "2021-12-08T13:15:14.779Z",
            "close_time": "2021-12-08T13:15:14.787Z",
            "commission": "10.0",
            "commission_currency": "USDT",
            "timestamp": "2021-12-08T13:15:14.785Z"
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("new", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["trade_size"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["trade_size"])) * Decimal(
            str(trade_event_info["trade_price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["commission"]), order.fee_paid)
        self.assertEqual(trade_event_info["commission_currency"], order.fee_asset)

        complete_event_info = {
            "order_id": "EOID1",
            "symbol": "BTCUSDT",
            "wallet_id": "8576DAF5-E033-46C6-8EFD-385F8A4662F7",
            "comment": "HBOT-buy-ETH-USDT-1638969314002553",
            "time_in_force": "good_till_cancel",
            "order_type": "limit",
            "side": "buy",
            "order_status": "completely_filled",
            "size": "1.0",
            "trade_size": "0.9",
            "trade_price": "10060.0",
            "limit_price": "10000",
            "stop_price": "None",
            "filled_size": "1",
            "average_price": "10000.0",
            "open_time": "2021-12-08T13:15:14.779Z",
            "close_time": "2021-12-08T13:15:14.787Z",
            "commission": "50.0",
            "commission_currency": "USDT",
            "timestamp": "2021-12-08T13:15:14.786Z"
        }

        update_result = order.update_with_trade_update(complete_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("new", order.last_state)
        self.assertEqual(order.amount, order.executed_amount_base)
        expected_executed_quote_amount += Decimal(str(complete_event_info["trade_size"])) * Decimal(
            str(complete_event_info["trade_price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["commission"]) + Decimal(complete_event_info["commission"]),
                         order.fee_paid)
        self.assertEqual(trade_event_info["commission_currency"], order.fee_asset)

    def test_update_with_repeated_timestamp_is_ignored(self):
        order = BeaxyInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1),
            created_at=datetime.now()
        )

        trade_event_info = {
            "order_id": "EOID1",
            "symbol": "BTCUSDT",
            "wallet_id": "8576DAF5-E033-46C6-8EFD-385F8A4662F7",
            "comment": "HBOT-buy-ETH-USDT-1638969314002553",
            "time_in_force": "good_till_cancel",
            "order_type": "limit",
            "side": "buy",
            "order_status": "partially_filled",
            "size": "1.0",
            "trade_size": "0.1",
            "trade_price": "10050.0",
            "limit_price": "10000",
            "stop_price": "None",
            "filled_size": "0.1",
            "average_price": "10000.0",
            "open_time": "2021-12-08T13:15:14.779Z",
            "close_time": "2021-12-08T13:15:14.787Z",
            "commission": "10.0",
            "commission_currency": "USDT",
            "timestamp": "2021-12-08T13:15:14.785Z"
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("new", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["trade_size"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["trade_size"])) * Decimal(
            str(trade_event_info["trade_price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["commission"]), order.fee_paid)
        self.assertEqual(trade_event_info["commission_currency"], order.fee_asset)

        complete_event_info = {
            "order_id": "EOID1",
            "symbol": "BTCUSDT",
            "wallet_id": "8576DAF5-E033-46C6-8EFD-385F8A4662F7",
            "comment": "HBOT-buy-ETH-USDT-1638969314002553",
            "time_in_force": "good_till_cancel",
            "order_type": "limit",
            "side": "buy",
            "order_status": "completely_filled",
            "size": "1.0",
            "trade_size": "0.9",
            "trade_price": "10060.0",
            "limit_price": "10000",
            "stop_price": "None",
            "filled_size": "0.1",
            "average_price": "10000.0",
            "open_time": "2021-12-08T13:15:14.779Z",
            "close_time": "2021-12-08T13:15:14.787Z",
            "commission": "50.0",
            "commission_currency": "USDT",
            "timestamp": "2021-12-08T13:15:14.785Z"
        }

        update_result = order.update_with_trade_update(complete_event_info)

        self.assertFalse(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("new", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["trade_size"])), order.executed_amount_base)
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["commission"]), order.fee_paid)
        self.assertEqual(trade_event_info["commission_currency"], order.fee_asset)

    def test_update_without_trade_info_is_ignored(self):
        order = BeaxyInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1),
            created_at=datetime.now()
        )

        trade_event_info = {
            "order_id": "EOID1",
            "symbol": "BTCUSDT",
            "wallet_id": "8576DAF5-E033-46C6-8EFD-385F8A4662F7",
            "comment": "HBOT-buy-ETH-USDT-1638969314002553",
            "time_in_force": "good_till_cancel",
            "order_type": "limit",
            "side": "buy",
            "order_status": "partially_filled",
            "size": "1.0",
            "trade_size": None,
            "trade_price": None,
            "limit_price": "10000",
            "stop_price": "None",
            "filled_size": "0.1",
            "average_price": "10000.0",
            "open_time": "2021-12-08T13:15:14.779Z",
            "close_time": "2021-12-08T13:15:14.787Z",
            "commission": "10.0",
            "commission_currency": "USDT",
            "timestamp": "2021-12-08T13:15:14.785Z"
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertFalse(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("new", order.last_state)
        self.assertEqual(Decimal(0), order.executed_amount_base)
        self.assertEqual(Decimal(0), order.executed_amount_quote)
        self.assertEqual(Decimal(0), order.fee_paid)
        self.assertIsNone(order.fee_asset)
