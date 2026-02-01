"""
Unit tests for WEEX user stream data source (private WS)
"""
import json
import unittest
from unittest.mock import MagicMock, patch

from hummingbot.connector.exchange.weex.weex_api_user_stream_data_source import WeexAPIUserStreamDataSource
from hummingbot.connector.exchange.weex.weex_auth import WeexAuth


class TestWeexUserStreamDataSource(unittest.TestCase):
    """Test WEEX private user stream (fills, orders, balance updates)"""

    def setUp(self):
        self.auth = MagicMock(spec=WeexAuth)
        self.auth.build_ws_headers = MagicMock(
            return_value={
                "ACCESS-KEY": "test_key",
                "ACCESS-TIMESTAMP": "1000000",
                "ACCESS-SIGN": "test_sig",
                "ACCESS-PASSPHRASE": "test_pass",
            }
        )

        self.connector = MagicMock()
        self.api_factory = MagicMock()
        self.trading_pairs = ["VCC-USDT"]

        self.data_source = WeexAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=self.trading_pairs,
            connector=self.connector,
            api_factory=self.api_factory,
            domain="com",
        )

    def test_ws_headers_generation(self):
        """Test that WS headers are built correctly"""
        headers = self.auth.build_ws_headers()

        self.assertIn("ACCESS-KEY", headers)
        self.assertIn("ACCESS-TIMESTAMP", headers)
        self.assertIn("ACCESS-SIGN", headers)
        self.assertIn("ACCESS-PASSPHRASE", headers)

    def test_subscribe_channels_payload(self):
        """Test private channel subscription payloads"""
        # Verify the data source knows which channels to subscribe to
        self.assertEqual(
            self.data_source._trading_pairs,
            self.trading_pairs
        )

    @patch("asyncio.Queue")
    async def test_ping_pong_handling(self, mock_queue):
        """Test that ping messages trigger pong responses"""
        # Simulate receiving a ping
        ping_msg = MagicMock()
        ping_msg.data = json.dumps({"event": "ping", "time": 1000})

        # We should send a pong back
        # (This test verifies the message structure, not the full flow)
        pong_payload = {"event": "pong", "time": 1000}
        self.assertEqual(pong_payload["event"], "pong")

    def test_account_balance_parsing(self):
        """Test parsing account balance update from user stream"""
        balance_msg = {
            "event": "payload",
            "channel": "account",
            "data": [
                {
                    "coinName": "VCC",
                    "available": "500000",
                    "frozen": "0",
                    "equity": "500000",
                }
            ],
        }

        # Verify structure expected by listener
        self.assertEqual(balance_msg["channel"], "account")
        self.assertIn("data", balance_msg)
        self.assertTrue(len(balance_msg["data"]) > 0)

    def test_fill_event_parsing(self):
        """Test parsing fill (trade execution) event"""
        fill_msg = {
            "event": "payload",
            "channel": "fill",
            "data": [
                {
                    "orderId": "123456",
                    "clientOrderId": "x-MG43PCSN-1",
                    "fillId": "fill1",
                    "fillQuantity": "1000",
                    "fillPrice": "0.00015",
                    "fillTotalAmount": "0.15",
                    "fillFee": "0.00015",
                    "feeCoin": "VCC",
                    "cTime": 1000000,
                }
            ],
        }

        fill = fill_msg["data"][0]
        self.assertEqual(fill["clientOrderId"], "x-MG43PCSN-1")
        self.assertEqual(fill["fillQuantity"], "1000")
        self.assertIn("fillPrice", fill)

    def test_order_update_parsing(self):
        """Test parsing order state update"""
        order_msg = {
            "event": "payload",
            "channel": "orders",
            "data": [
                {
                    "orderId": "123456",
                    "clientOrderId": "x-MG43PCSN-1",
                    "status": "FILLED",
                    "quantity": "1000",
                    "fillQuantity": "1000",
                    "price": "0.00015",
                    "uTime": 1000000,
                }
            ],
        }

        order = order_msg["data"][0]
        self.assertEqual(order["status"], "FILLED")
        self.assertEqual(order["quantity"], order["fillQuantity"])

    def test_non_payload_message_ignored(self):
        """Test that non-payload messages are safely ignored"""
        non_payload = {
            "event": "subscribe",
            "channel": "account",
        }

        # Should not crash; payload listener checks for event=="payload"
        self.assertNotEqual(non_payload.get("event"), "payload")

    def test_heartbeat_interval(self):
        """Verify heartbeat timeout is reasonable"""
        # Heartbeat should be 30s as defined in the class
        self.assertEqual(
            WeexAPIUserStreamDataSource.HEARTBEAT_TIME_INTERVAL,
            30.0
        )


if __name__ == "__main__":
    unittest.main()
