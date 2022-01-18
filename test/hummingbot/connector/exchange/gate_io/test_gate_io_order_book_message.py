from unittest import TestCase

from hummingbot.connector.exchange.gate_io.gate_io_order_book import GateIoOrderBook


class GateIoOrderBookTests(TestCase):

    def test_snapshot_message_equality_with_snapshot_message(self):
        id_a = 123456
        id_b = 234567
        timestamp_a = 1623898900000
        timestamp_b = 1623899000000

        message_dict = {
            "id": id_a,
            "current": timestamp_a,
            "update": 1623898993121,
            "asks": [],
            "bids": []
        }

        message = GateIoOrderBook.snapshot_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["current"] * 1e-3,
        )

        equal_message = GateIoOrderBook.snapshot_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["current"] * 1e-3,
        )

        self.assertEqual(message, equal_message)
        self.assertEqual(hash(message), hash(equal_message))

        message_dict = {
            "id": id_b,
            "current": timestamp_a,
            "update": 1623898993121,
            "asks": [],
            "bids": []
        }

        different_id_message = GateIoOrderBook.snapshot_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["current"] * 1e-3,
        )

        self.assertNotEqual(message, different_id_message)

        message_dict = {
            "id": id_a,
            "current": timestamp_b,
            "update": 1623898993121,
            "asks": [],
            "bids": []
        }

        different_timestamp_message = GateIoOrderBook.snapshot_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["current"] * 1e-3,
        )

        self.assertNotEqual(message, different_timestamp_message)

    def test_diff_message_equality_with_diff_message(self):
        id_a = 123456
        id_b = 234567
        timestamp_a = 1623898900000
        timestamp_b = 1623899000000

        message_dict = {
            "t": timestamp_a,
            "e": "depthUpdate",
            "E": 1606294781,
            "s": "BTC_USDT",
            "U": 48776301,
            "u": id_a,
            "b": [],
            "a": []
        }

        message = GateIoOrderBook.diff_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["t"] * 1e-3,
        )

        equal_message = GateIoOrderBook.diff_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["t"] * 1e-3,
        )

        self.assertEqual(message, equal_message)
        self.assertEqual(hash(message), hash(equal_message))

        message_dict = {
            "t": timestamp_a,
            "e": "depthUpdate",
            "E": 1606294781,
            "s": "BTC_USDT",
            "U": 48776301,
            "u": id_b,
            "b": [],
            "a": []
        }

        different_id_message = GateIoOrderBook.diff_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["t"] * 1e-3,
        )

        self.assertNotEqual(message, different_id_message)

        message_dict = {
            "t": timestamp_b,
            "e": "depthUpdate",
            "E": 1606294781,
            "s": "BTC_USDT",
            "U": 48776301,
            "u": id_a,
            "b": [],
            "a": []
        }

        different_timestamp_message = GateIoOrderBook.diff_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["t"] * 1e-3,
        )

        self.assertNotEqual(message, different_timestamp_message)

    def test_trade_message_equality_with_trade_message(self):
        timestamp_a = 1623898900
        timestamp_b = 1623899000

        message_dict = {
            "id": 5736713,
            "user_id": 1000001,
            "order_id": "30784428",
            "currency_pair": "BTC_USDT",
            "create_time": timestamp_a,
            "create_time_ms": "1605176741123.456",
            "side": "sell",
            "amount": "1.00000000",
            "role": "taker",
            "price": "10000.00000000",
            "fee": "0.00200000000000",
            "point_fee": "0",
            "gt_fee": "0",
            "text": "apiv4"
        }

        message = GateIoOrderBook.trade_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["create_time"],
        )

        equal_message = GateIoOrderBook.trade_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["create_time"],
        )

        self.assertEqual(message, equal_message)
        self.assertEqual(hash(message), hash(equal_message))

        message_dict = {
            "id": 5736713,
            "user_id": 1000001,
            "order_id": "30784428",
            "currency_pair": "BTC_USDT",
            "create_time": timestamp_b,
            "create_time_ms": "1605176741123.456",
            "side": "sell",
            "amount": "1.00000000",
            "role": "taker",
            "price": "10000.00000000",
            "fee": "0.00200000000000",
            "point_fee": "0",
            "gt_fee": "0",
            "text": "apiv4"
        }

        different_timestamp_message = GateIoOrderBook.trade_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["create_time"],
        )

        self.assertNotEqual(message, different_timestamp_message)

    def test_different_type_messages_are_not_equal(self):
        id = 123456
        timestamp = 1623898900000

        message_dict = {
            "id": id,
            "current": timestamp,
            "update": 1623898993121,
            "asks": [],
            "bids": []
        }

        snapshot_message = GateIoOrderBook.snapshot_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["current"] * 1e-3,
        )

        message_dict = {
            "t": timestamp,
            "e": "depthUpdate",
            "E": 1606294781,
            "s": "BTC_USDT",
            "U": 48776301,
            "u": id,
            "b": [],
            "a": []
        }

        diff_message = GateIoOrderBook.diff_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["t"] * 1e-3,
        )

        message_dict = {
            "id": 5736713,
            "user_id": 1000001,
            "order_id": "30784428",
            "currency_pair": "BTC_USDT",
            "create_time": timestamp,
            "create_time_ms": "1605176741123.456",
            "side": "sell",
            "amount": "1.00000000",
            "role": "taker",
            "price": "10000.00000000",
            "fee": "0.00200000000000",
            "point_fee": "0",
            "gt_fee": "0",
            "text": "apiv4"
        }

        trade_message = GateIoOrderBook.trade_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["create_time"],
        )

        self.assertNotEqual(snapshot_message, diff_message)
        self.assertNotEqual(diff_message, trade_message)
        self.assertNotEqual(snapshot_message, trade_message)

    def test_less_than_compares_update_id_and_timestamp_and_type(self):
        id_a = 123456
        id_b = 234567
        timestamp_a = 1623898900000
        timestamp_b = 1623899000000

        message_dict = {
            "id": id_a,
            "current": timestamp_a,
            "update": 1623898993121,
            "asks": [],
            "bids": []
        }

        message = GateIoOrderBook.snapshot_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["current"] * 1e-3,
        )

        message_dict = {
            "id": id_b,
            "current": timestamp_a,
            "update": 1623898993121,
            "asks": [],
            "bids": []
        }

        greater_id_message = GateIoOrderBook.snapshot_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["current"] * 1e-3,
        )

        self.assertLess(message, greater_id_message)

        message_dict = {
            "id": id_a,
            "current": timestamp_b,
            "update": 1623898993121,
            "asks": [],
            "bids": []
        }

        equal_id_greater_timestamp_message = GateIoOrderBook.snapshot_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["current"] * 1e-3,
        )

        self.assertLess(message, equal_id_greater_timestamp_message)

        message_dict = {
            "t": timestamp_a,
            "e": "depthUpdate",
            "E": 1606294781,
            "s": "BTC_USDT",
            "U": 48776301,
            "u": id_a,
            "b": [],
            "a": []
        }

        same_id_and_timestamp_diff_message = GateIoOrderBook.diff_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["t"] * 1e-3,
        )

        self.assertLess(message, same_id_and_timestamp_diff_message)
