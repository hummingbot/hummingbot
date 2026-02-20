import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_user_stream_data_source import (
    DecibelPerpetualUserStreamDataSource,
)


class TestDecibelPerpetualUserStreamDataSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self):
        self.auth = DecibelPerpetualAuth(
            api_key="test_api_key",
            account_address="0xtest_account",
            subaccount_address="0xtest_subaccount",
            private_key="0xtest_private_key",
        )
        self.connector = MagicMock()
        self.connector.decibel_account_address = "0xtest_account"
        self.api_factory = MagicMock()
        self.data_source = DecibelPerpetualUserStreamDataSource(
            auth=self.auth,
            trading_pairs=["BTC-USD"],
            connector=self.connector,
            api_factory=self.api_factory,
            domain=CONSTANTS.DOMAIN,
        )

    def test_last_recv_time_default(self):
        self.assertEqual(self.data_source.last_recv_time, 0)

    def test_process_event_message_order_update(self):
        queue = asyncio.Queue()
        event = {
            "topic": f"{CONSTANTS.WS_ORDER_UPDATE_TOPIC}:0xtest_account",
            "data": {
                "order_id": "order_001",
                "status": "filled",
                "client_order_id": "HBOT_001",
            },
        }
        self.ev_loop.run_until_complete(
            self.data_source._process_event_message(event, queue)
        )
        self.assertFalse(queue.empty())
        msg = queue.get_nowait()
        self.assertEqual(msg["topic"], f"{CONSTANTS.WS_ORDER_UPDATE_TOPIC}:0xtest_account")

    def test_process_event_message_positions(self):
        queue = asyncio.Queue()
        event = {
            "topic": f"{CONSTANTS.WS_ACCOUNT_POSITIONS_TOPIC}:0xtest_account",
            "data": [{"market": "BTC-PERP", "size": "1.0"}],
        }
        self.ev_loop.run_until_complete(
            self.data_source._process_event_message(event, queue)
        )
        self.assertFalse(queue.empty())

    def test_process_event_message_overview(self):
        queue = asyncio.Queue()
        event = {
            "topic": f"{CONSTANTS.WS_ACCOUNT_OVERVIEW_TOPIC}:0xtest_account",
            "data": {"equity": "10000.0", "available_balance": "5000.0"},
        }
        self.ev_loop.run_until_complete(
            self.data_source._process_event_message(event, queue)
        )
        self.assertFalse(queue.empty())

    def test_process_event_message_error(self):
        queue = asyncio.Queue()
        event = {"error": {"message": "Unauthorized"}}
        with self.assertRaises(IOError):
            self.ev_loop.run_until_complete(
                self.data_source._process_event_message(event, queue)
            )

    def test_process_event_message_irrelevant_topic(self):
        queue = asyncio.Queue()
        event = {"topic": "some_other_topic:0xtest", "data": {}}
        self.ev_loop.run_until_complete(
            self.data_source._process_event_message(event, queue)
        )
        self.assertTrue(queue.empty())


if __name__ == "__main__":
    unittest.main()
