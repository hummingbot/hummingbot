import asyncio
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.mixin_ws_operations import (
    MixinWSOperations,
    parse_websocket_message,
)
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.protocols import ProtocolWSAssistant


class TestParseWebsocketMessage(IsolatedAsyncioWrapperTestCase):
    """Test suite for parse_websocket_message function."""

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()

    def test_valid_single_candle(self):
        """Test parsing message with a single valid candle."""
        message = {
            "events": [{
                "candles": [{
                    "start": 1700000000,
                    "open": "100.0",
                    "high": "101.0",
                    "low": "99.0",
                    "close": "100.5",
                    "volume": "1000.0"
                }]
            }]
        }

        candles = list(parse_websocket_message(message))

        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].timestamp, 1700000000)

    def test_multiple_candles(self):
        """Test parsing message with multiple candles."""
        message = {
            "events": [{
                "candles": [
                    {
                        "start": 1700000000,
                        "open": "100.0",
                        "high": "101.0",
                        "low": "99.0",
                        "close": "100.5",
                        "volume": "1000.0"
                    },
                    {
                        "start": 1700000300,
                        "open": "100.5",
                        "high": "102.0",
                        "low": "100.0",
                        "close": "101.5",
                        "volume": "1100.0"
                    }
                ]
            }]
        }

        candles = list(parse_websocket_message(message))

        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[0].timestamp, 1700000000)
        self.assertEqual(candles[1].timestamp, 1700000300)


#    def test_invalid_inputs(self):
#        """Test handling of various invalid inputs."""
#        test_cases = [
#            (None, "None input"),
#            ({}, "Empty dict"),
#            ({"wrong_key": []}, "Missing events key"),
#            ({"events": []}, "Empty events"),
#            ({"events": [{"wrong_key": []}]}, "Missing candles key"),
#            ({"events": [{"candles": []}]}, "Empty candles"),
#            ({"events": [None]}, "None event"),
#            ({"events": [{"candles": [None]}]}, "None candle"),
#        ]
#
#        for message, description in test_cases:
#            with self.subTest(description):
#                candles = list(parse_websocket_message(message))
#                self.assertEqual(len(candles), 0, f"Failed for: {description}")


class MockWSOperations(MixinWSOperations):
    """Mock class implementing required protocol properties."""

    def __init__(self):
        self._api_factory = MagicMock()
        self._connected_websocket_assistant = AsyncMock()
        self._subscribe_channels = AsyncMock()
        self._on_order_stream_interruption = AsyncMock()
        self._sleep = AsyncMock()
        self._logger = MagicMock()
        self._initialize_deque_from_sequence = AsyncMock()

        # Mock interval as property
        self._interval = "5m"

    @property
    def interval(self) -> str:
        return self._interval

    def get_seconds_from_interval(self, interval: str) -> int:
        return 300

    def logger(self):
        return self._logger


async def async_message_iterator(messages):
    """Create an async iterator from a list of messages."""
    for message in messages:
        yield message


class TestMixinWSOperations(IsolatedAsyncioWrapperTestCase):
    """Test suite for MixinWSOperations class."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.mock_ws = AsyncMock(spec=ProtocolWSAssistant)
        self.mixin = MockWSOperations()

        # Setup websocket assistant
        self.mixin._connected_websocket_assistant.return_value = self.mock_ws

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()

    async def test__catsc_process_websocket_messages(self):
        """Test processing of websocket messages."""
        # Create a sequence of test messages
        valid_candle = {
            "events": [{
                "candles": [{
                    "start": 1700000000,
                    "open": "100.0",
                    "high": "101.0",
                    "low": "99.0",
                    "close": "100.5",
                    "volume": "1000.0"
                }]
            }]
        }
        json_request = WSJSONRequest({"type": "subscribe"})
        invalid_message = {"wrong_key": "value"}

        messages = [
            MagicMock(data=valid_candle),
            MagicMock(data=json_request),
            MagicMock(data=invalid_message),
        ]

        # Create async iterator for messages
        self.mock_ws.iter_messages.return_value = async_message_iterator(messages)

        # Need to break the infinite loop, so we'll cancel after processing messages
        async def cancel_after_delay():
            await asyncio.sleep(0.1)
            raise asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await asyncio.gather(
                self.mixin._catsc_process_websocket_messages(self.mock_ws),
                cancel_after_delay()
            )

        # Verify behavior
        self.mock_ws.send.assert_called_once_with(request=json_request)
        self.mixin._initialize_deque_from_sequence.assert_called()

    async def test_listen_for_subscriptions(self):
        """Test websocket subscription listening.

        Tests both normal operation and error cases by controlling
        the number of iterations through the loop.
        """
        mock_ws = AsyncMock(spec=ProtocolWSAssistant)
        self.mixin._connected_websocket_assistant = AsyncMock(return_value=mock_ws)

        # Set up the message iteration to run a few times then cancel
        messages_processed = 0

        async def mock_process_messages(websocket_assistant):
            nonlocal messages_processed
            messages_processed += 1
            if messages_processed >= 2:  # Process 2 messages then cancel
                raise asyncio.CancelledError()

        self.mixin._catsc_process_websocket_messages = mock_process_messages

        # Test normal flow with cancellation
        with self.assertRaises(asyncio.CancelledError):
            await self.mixin._catsc_listen_for_subscriptions()

        # Verify the expected calls were made
        self.mixin._connected_websocket_assistant.assert_called()
        self.mixin._subscribe_channels.assert_called()
        self.mixin._on_order_stream_interruption.assert_called()

    async def test_listen_for_subscriptions_connection_error(self):
        """Test that connection errors are handled and loop continues."""
        mock_ws = AsyncMock(spec=ProtocolWSAssistant)

        connection_attempts = 0

        async def mock_connection():
            nonlocal connection_attempts
            connection_attempts += 1
            if connection_attempts in {2, 3}:  # Fail on 2nd and 3rd attempts
                raise ConnectionError("Test connection error")
            return mock_ws

        self.mixin._connected_websocket_assistant = AsyncMock(side_effect=mock_connection)

        messages_processed = 0

        async def mock_process_messages(websocket_assistant):
            nonlocal messages_processed
            messages_processed += 1
            if messages_processed >= 4:  # Stop after 4 iterations (including errors)
                raise asyncio.CancelledError()

        self.mixin._catsc_process_websocket_messages = mock_process_messages

        # Run until CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await self.mixin._catsc_listen_for_subscriptions()

        # Verify:
        # - Multiple connection attempts were made
        # - Warnings were logged for connection errors
        # - Loop continued after errors
        self.assertGreater(connection_attempts, 3)
        self.mixin.logger().warning.assert_called()
        self.assertEqual(messages_processed, 4)
        self.mixin._on_order_stream_interruption.assert_called()

    async def test_cancellation(self):
        """Test handling of cancellation."""
        self.mock_ws.iter_messages.side_effect = asyncio.CancelledError()

        with self.assertRaises(asyncio.CancelledError):
            await self.mixin._catsc_listen_for_subscriptions()

        self.mixin._on_order_stream_interruption.assert_called_once()

    async def test_message_handling_sequence(self):
        """Test the complete sequence of message handling."""
        # Create a sequence of different message types
        messages = [
            # Valid candle
            MagicMock(data={
                "events": [{
                    "candles": [{
                        "start": 1700000000,
                        "open": "100.0",
                        "high": "101.0",
                        "low": "99.0",
                        "close": "100.5",
                        "volume": "1000.0"
                    }]
                }]
            }),
            # JSON request
            MagicMock(data=WSJSONRequest({"type": "subscribe"})),
            # Invalid message
            MagicMock(data={"wrong_key": "value"}),
            # Empty events
            MagicMock(data={"events": []}),
            # None data
            MagicMock(data=None),
        ]

        self.mock_ws.iter_messages.return_value = async_message_iterator(messages)

        async def cancel_after_messages():
            await asyncio.sleep(0.1)
            raise asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await asyncio.gather(
                self.mixin._catsc_process_websocket_messages(self.mock_ws),
                cancel_after_messages()
            )

        # Verify all message types were handled correctly
        self.mock_ws.send.assert_called_once()  # Should be called for JSON request
        self.mixin._initialize_deque_from_sequence.assert_called_once()  # Should be called for valid candle


if __name__ == '__main__':
    unittest.main()
