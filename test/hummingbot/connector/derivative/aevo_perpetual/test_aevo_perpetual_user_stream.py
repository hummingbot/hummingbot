import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio
from typing import Optional
import test.hummingbot.connector.derivative.aevo_perpetual.mock_utils # Ensure mocks are loaded
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_user_stream_data_source import AevoPerpetualUserStreamDataSource
from hummingbot.connector.derivative.aevo_perpetual import aevo_perpetual_constants as CONSTANTS

class TestAevoPerpetualUserStreamDataSource(unittest.TestCase):
    def setUp(self):
        self.mock_auth = MagicMock() # Use MagicMock for synchronous methods
        self.mock_auth.get_ws_auth_payload.return_value = {"op": "auth", "data": "mock_auth_data"}
        self.trading_pairs = ["ETH-USD"]
        self.mock_api_factory = AsyncMock()
        self.mock_ws_connection = AsyncMock()
        self.mock_api_factory.get_ws_connection.return_value = self.mock_ws_connection
        self.user_stream = AevoPerpetualUserStreamDataSource(
            auth=self.mock_auth,
            trading_pairs=self.trading_pairs,
            api_factory=self.mock_api_factory
        )

    @patch("hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_user_stream_data_source.AevoPerpetualUserStreamDataSource._sleep")
    def test_listen_to_user_messages_authenticates_and_subscribes(self, mock_sleep):
        # Setup mock behavior
        self.mock_ws_connection.connect = AsyncMock()
        self.mock_ws_connection.send_json = AsyncMock()
        # Mock iter_messages to return one message then raise CancelledError to stop loop
        async def mock_iter_messages():
            yield AsyncMock(data="{\"channel\": \"orders\"}")
            raise asyncio.CancelledError()
            
        self.mock_ws_connection.iter_messages = mock_iter_messages
        
        output_queue = asyncio.Queue()
        
        # Run the method
        try:
            asyncio.get_event_loop().run_until_complete(
                self.user_stream._listen_to_user_messages(output_queue)
            )
        except asyncio.CancelledError:
            pass

        # Verify Auth was called
        self.mock_auth.get_ws_auth_payload.assert_called_once()
        # Verify Auth message sent
        print(f"DEBUG calls: {self.mock_ws_connection.send_json.call_args_list}") 
        self.mock_ws_connection.send_json.assert_any_call({"op": "auth", "data": "mock_auth_data"})
        
        # Verify Subscription message sent
        expected_subscription = {
            "op": "subscribe",
            "data": ["orders", "fills", "positions", "account"]
        }
        self.mock_ws_connection.send_json.assert_any_call(expected_subscription)

