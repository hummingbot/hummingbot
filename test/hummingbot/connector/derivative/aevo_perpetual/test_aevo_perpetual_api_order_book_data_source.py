import unittest
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock, patch
import sys
from types import ModuleType

# --- MOCKING DEPENDENCIES START ---
import test.hummingbot.connector.derivative.aevo_perpetual.mock_utils
from test.hummingbot.connector.derivative.aevo_perpetual.mock_utils import MockOrderBookMessageType
from unittest.mock import MagicMock

# Additional specific mocks for OrderBook
mock_ob_msg_module = ModuleType("hummingbot.core.data_type.order_book_message")
mock_ob_tracker_module = ModuleType("hummingbot.core.data_type.order_book_tracker_data_source")
mock_throttler_module = ModuleType("hummingbot.core.api_throttler.async_throttler")
mock_ob_module = ModuleType("hummingbot.core.data_type.order_book")

class MockOrderBook:
    pass

class MockOrderBookMessage:
    def __init__(self, msg_type, content, timestamp=0):
        self.type = msg_type
        self.content = content
        self.timestamp = timestamp

class MockOrderBookMessageType:
    SNAPSHOT = 1
    TRADE = 2

class MockOrderBookTrackerDataSource:
    def __init__(self, trading_pairs):
        self._trading_pairs = trading_pairs

mock_ob_msg_module.OrderBookMessage = MockOrderBookMessage
mock_ob_msg_module.OrderBookMessageType = MockOrderBookMessageType
mock_ob_tracker_module.OrderBookTrackerDataSource = MockOrderBookTrackerDataSource
mock_throttler_module.AsyncThrottler = MagicMock
mock_ob_module.OrderBook = MockOrderBook

sys.modules["hummingbot.core.data_type.order_book_message"] = mock_ob_msg_module
sys.modules["hummingbot.core.data_type.order_book_tracker_data_source"] = mock_ob_tracker_module
sys.modules["hummingbot.core.api_throttler.async_throttler"] = mock_throttler_module
sys.modules["hummingbot.core.data_type.order_book"] = mock_ob_module
# --- MOCKING END ---

from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_api_order_book_data_source import AevoPerpetualAPIOrderBookDataSource
from hummingbot.connector.derivative.aevo_perpetual import aevo_perpetual_constants as CONSTANTS

class AevoDataSourceTest(unittest.TestCase):
    def setUp(self):
        self.api_factory = MagicMock()
        self.throttler = MagicMock()
        self.time_synchronizer = MagicMock()
        self.time_synchronizer.time.return_value = 1600000000.0
        
        self.data_source = AevoPerpetualAPIOrderBookDataSource(
            trading_pairs=["ETH-PERP"],
            domain="aevo",
            api_factory=self.api_factory,
            throttler=self.throttler,
            time_synchronizer=self.time_synchronizer
        )
        self.data_source.logger = MagicMock()
        self.data_source._message_queue = asyncio.Queue()

    def test_parse_order_book_snapshot(self):
        # Mock WS connection
        mock_ws = AsyncMock()
        self.api_factory.get_ws_connection.return_value = mock_ws
        
        # Simulate a snapshot message
        # Payload structure based on implementation: {"data": {"type": "snapshot", ...}, "channel": "orderbook:ETH-PERP"}
        msg_content = {
            "channel": f"{CONSTANTS.WS_TOPIC_ORDERBOOK}:ETH-PERP",
            "data": {
                "type": "snapshot",
                "timestamp": 1600000000000000000,
                "bids": [["2000", "1"]],
                "asks": [["2001", "1"]]
            }
        }
        
        # Mock iter_messages to yield this message then simulate cancel/stop
        async def iter_messages():
            mock_msg = MagicMock()
            mock_msg.data = True
            mock_msg.json.return_value = msg_content
            yield mock_msg
            # Break loop by raising CancelledError or just stopping if loop logic handles it
            # The loop is 'while True', so we need to raise CancelledError to exit cleanly in test
            raise asyncio.CancelledError
            
        mock_ws.iter_messages = iter_messages
        mock_ws.connect = AsyncMock()
        mock_ws.send_json = AsyncMock()

        # Run listener
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.data_source.listen_for_subscriptions())
            loop.close()
        except asyncio.CancelledError:
            pass
            
        # Verify message queue has the parsed message
        self.assertFalse(self.data_source._message_queue.empty())
        msg = self.data_source._message_queue.get_nowait()
        
        self.assertEqual(msg.type, MockOrderBookMessageType.SNAPSHOT)
        self.assertEqual(msg.content["trading_pair"], "ETH-PERP")
        self.assertEqual(len(msg.content["bids"]), 1)
        self.assertEqual(msg.content["bids"][0][0], "2000")

    def test_parse_trades(self):
        mock_ws = AsyncMock()
        self.api_factory.get_ws_connection.return_value = mock_ws
        
        msg_content = {
            "channel": f"{CONSTANTS.WS_TOPIC_TRADES}:ETH-PERP",
            "data": [
                {
                    "trade_id": "123",
                    "price": "2000.5",
                    "amount": "0.1",
                    "side": "buy",
                    "timestamp": 1600000000000000000
                }
            ]
        }
        
        async def iter_messages():
            mock_msg = MagicMock()
            mock_msg.data = True
            mock_msg.json.return_value = msg_content
            yield mock_msg
            raise asyncio.CancelledError
            
        mock_ws.iter_messages = iter_messages
        mock_ws.connect = AsyncMock()

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.data_source.listen_for_subscriptions())
            loop.close()
        except asyncio.CancelledError:
            pass
            
        self.assertFalse(self.data_source._message_queue.empty())
        msg = self.data_source._message_queue.get_nowait()
        
        self.assertEqual(msg.type, MockOrderBookMessageType.TRADE)
        self.assertEqual(msg.content["trading_pair"], "ETH-PERP")
        self.assertEqual(msg.content["trade_id"], "123")
        self.assertEqual(msg.content["price"], "2000.5")
