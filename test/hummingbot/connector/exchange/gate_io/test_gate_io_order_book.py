from unittest import TestCase

from hummingbot.connector.exchange.gate_io.gate_io_order_book import GateIoOrderBook


class GateIoOrderBookTests(TestCase):

    def test_snapshot_message_creation_from_exchange(self):
        message_dict = {
            "id": 123456,
            "current": 1623898993123,
            "update": 1623898993121,
            "asks": [
                [
                    "1.52",
                    "1.151"
                ],
                [
                    "1.53",
                    "1.218"
                ]
            ],
            "bids": [
                [
                    "1.17",
                    "201.863"
                ],
                [
                    "1.16",
                    "725.464"
                ]
            ]
        }

        message = GateIoOrderBook.snapshot_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["current"] * 1e-3,
        )

        self.assertEqual(message_dict["id"], message.update_id)
        self.assertEqual(message_dict["current"] * 1e-3, message.timestamp)

    def test_diff_message_creation_from_exchange(self):
        message_dict = {
            "t": 1606294781123,
            "e": "depthUpdate",
            "E": 1606294781,
            "s": "BTC_USDT",
            "U": 48776301,
            "u": 48776306,
            "b": [
                [
                    "19137.74",
                    "0.0001"
                ],
                [
                    "19088.37",
                    "0"
                ]
            ],
            "a": [
                [
                    "19137.75",
                    "0.6135"
                ]
            ]
        }

        message = GateIoOrderBook.diff_message_from_exchange(
            msg=message_dict,
            timestamp=message_dict["t"] * 1e-3,
        )

        self.assertEqual(message_dict["u"], message.update_id)
        self.assertEqual(message_dict["t"] * 1e-3, message.timestamp)
