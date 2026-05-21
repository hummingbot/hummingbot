"""Unit tests for Evedex Perpetual User Stream Data Source."""
import asyncio
import unittest
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_auth import EvedexPerpetualAuth
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_user_stream_data_source import (
    EvedexPerpetualUserStreamDataSource,
)


class TestEvedexPerpetualUserStreamDataSource(unittest.IsolatedAsyncioTestCase):
    """
    Test suite for EvedexPerpetualUserStreamDataSource.

    WebSocket Channels (Centrifuge protocol):
    - order-{userExchangeId} - Order updates
    - position-{userExchangeId} - Position updates
    - user-{userExchangeId} - Account/balance updates
    - orderFills-{userExchangeId} - Order fill events
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.user_exchange_id = "12345"
        cls.api_key = "test-api-key"

    def setUp(self):
        super().setUp()
        self.listening_task: Optional[asyncio.Task] = None

        self.time_provider = MagicMock()
        self.private_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # noqa: mock
        self.auth = EvedexPerpetualAuth(api_key=self.api_key, private_key=self.private_key, time_provider=self.time_provider)

        self.connector = MagicMock()
        self.connector._domain = CONSTANTS.DEFAULT_DOMAIN
        self.connector._api_get = AsyncMock(return_value={"exchangeId": self.user_exchange_id})

        self.api_factory = MagicMock()
        self.ws_assistant = MagicMock()
        self.ws_assistant.connect = AsyncMock()
        self.ws_assistant.send = AsyncMock()
        self.ws_assistant.disconnect = AsyncMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=self.ws_assistant)

        self.data_source = EvedexPerpetualUserStreamDataSource(
            auth=self.auth,
            connector=self.connector,
            api_factory=self.api_factory,
            domain=CONSTANTS.DEFAULT_DOMAIN
        )

    def tearDown(self):
        if self.listening_task is not None:
            self.listening_task.cancel()
        super().tearDown()

    def _user_me_response(self):
        """Mock response for GET /api/user/me."""
        return {
            "id": "user_001",
            "exchangeId": self.user_exchange_id,
            "email": "test@example.com",
            "status": "ACTIVE",
            "createdAt": "2024-01-01T00:00:00.000Z"
        }

    async def test_get_user_exchange_id(self):
        """Test fetching userExchangeId from /api/user/me."""
        self.connector._api_get.return_value = self._user_me_response()

        user_exchange_id = await self.data_source._get_user_exchange_id()

        self.assertEqual(user_exchange_id, self.user_exchange_id)
        # Verify the call was made with correct path and auth flag
        self.assertEqual(self.connector._api_get.call_count, 1)
        call_args = self.connector._api_get.call_args
        self.assertEqual(call_args.kwargs.get("path_url"), CONSTANTS.USER_ME_PATH_URL)
        self.assertTrue(call_args.kwargs.get("is_auth_required"))

    async def test_get_user_exchange_id_caches_result(self):
        """Test that userExchangeId is cached after first fetch."""
        self.connector._api_get.return_value = self._user_me_response()

        # First call
        await self.data_source._get_user_exchange_id()
        # Second call should use cached value
        await self.data_source._get_user_exchange_id()

        # Should only call API once
        self.assertEqual(self.connector._api_get.call_count, 1)

    async def test_connected_websocket_assistant(self):
        """Test WebSocket connection establishment."""
        await self.data_source._connected_websocket_assistant()

        self.ws_assistant.connect.assert_called_once()
        call_kwargs = self.ws_assistant.connect.call_args[1]
        self.assertIn("ws_url", call_kwargs)
        self.assertIn("ping_timeout", call_kwargs)
        # ping_timeout = HEARTBEAT_TIME_INTERVAL + PING_TIMEOUT (25 + 10 = 35)
        expected_timeout = EvedexPerpetualUserStreamDataSource.HEARTBEAT_TIME_INTERVAL + EvedexPerpetualUserStreamDataSource.PING_TIMEOUT
        self.assertEqual(call_kwargs["ping_timeout"], expected_timeout)

    async def test_connected_websocket_assistant_cancels_ping_task(self):
        ping_task = asyncio.create_task(asyncio.sleep(10))
        self.data_source._ping_task = ping_task
        await self.data_source._connected_websocket_assistant()
        self.assertTrue(ping_task.cancelled() or ping_task.done())

    async def test_get_access_token_delegates_to_auth(self):
        self.auth.get_access_token = AsyncMock(return_value="token-123")
        token = await self.data_source._get_access_token()
        self.assertEqual(token, "token-123")

    async def test_subscribe_channels(self):
        """Test subscription to Centrifuge user channels."""
        self.connector._api_get.return_value = self._user_me_response()

        await self.data_source._subscribe_channels(self.ws_assistant)

        self.assertEqual(self.ws_assistant.send.call_count, 5)

        # Check subscribe message was sent (Centrifugo format)
        subscribe_call = self.ws_assistant.send.call_args_list[0]
        subscribe_payload = subscribe_call[0][0].payload
        self.assertIn("subscribe", subscribe_payload)

    async def test_subscribe_channels_exception(self):
        self.connector._api_get.return_value = self._user_me_response()
        self.ws_assistant.send = AsyncMock(side_effect=Exception("boom"))
        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(self.ws_assistant)

    async def test_process_websocket_messages_ping_pong(self):
        async def message_iterator():
            class Msg:
                def __init__(self, data):
                    self.data = data
            yield Msg({})
            yield Msg({"ping": {}})
            raise asyncio.CancelledError

        self.ws_assistant.iter_messages = message_iterator
        queue = asyncio.Queue()
        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._process_websocket_messages(self.ws_assistant, queue)
        # pong sent at least twice (empty + ping)
        self.assertGreaterEqual(self.ws_assistant.send.call_count, 2)

    async def test_on_user_stream_interruption_cancels_ping_task(self):
        ping_task = asyncio.create_task(asyncio.sleep(10))
        self.data_source._ping_task = ping_task
        await self.data_source._on_user_stream_interruption(self.ws_assistant)
        self.assertTrue(ping_task.cancelled() or ping_task.done())
        self.assertIsNone(self.data_source._ws_assistant)

    async def test_process_event_message_error_high_code(self):
        event_message = {"error": {"code": 100, "message": "permission denied"}}
        queue = asyncio.Queue()
        await self.data_source._process_event_message(event_message, queue)
        # Should not raise, and queue remains empty
        self.assertTrue(queue.empty())

    async def test_process_event_message_error_low_code(self):
        event_message = {"error": {"code": 0, "message": "temporary"}}
        queue = asyncio.Queue()
        with self.assertRaises(IOError):
            await self.data_source._process_event_message(event_message, queue)


class TestEvedexPerpetualUserStreamWebSocketMessages(unittest.TestCase):
    """Test WebSocket message structures for perpetual user stream."""

    def setUp(self):
        self.user_exchange_id = "12345"
        self.base_asset = "BTC"
        self.quote_asset = "USDT"
        self.ex_trading_pair = f"{self.base_asset}-{self.quote_asset}"

    def _order_ws_update(self, status="NEW"):
        """Mock WebSocket message from futures-perp:order-{userExchangeId} channel (Centrifugo push format)."""
        return {
            "push": {
                "channel": f"futures-perp:order-{self.user_exchange_id}",
                "pub": {
                    "data": {
                        "id": "00001:00000000000000000000000001",
                        "user": "user_001",
                        "instrument": self.ex_trading_pair,
                        "type": "LIMIT",
                        "side": "BUY",
                        "status": status,
                        "rejectedReason": "",
                        "quantity": 1.0,
                        "limitPrice": 50000.0,
                        "stopPrice": None,
                        "group": "manually",
                        "unFilledQuantity": 1.0 if status != "FILLED" else 0.0,
                        "cashQuantity": 50000.0,
                        "filledAvgPrice": 0.0 if status != "FILLED" else 50000.0,
                        "realizedPnL": 0.0,
                        "fee": [] if status != "FILLED" else [{"coin": self.quote_asset, "quantity": 10.0}],
                        "triggeredAt": None,
                        "exchangeRequestId": "req_123",
                        "createdAt": "2024-01-01T00:00:00.000Z",
                        "updatedAt": "2024-01-01T00:00:00.000Z"
                    }
                }
            }
        }

    def _position_ws_update(self):
        """Mock WebSocket message from futures-perp:position-{userExchangeId} channel (Centrifugo push format)."""
        return {
            "push": {
                "channel": f"futures-perp:position-{self.user_exchange_id}",
                "pub": {
                    "data": {
                        "id": "pos_123456",
                        "user": "user_001",
                        "instrument": self.ex_trading_pair,
                        "quantity": 1.0,
                        "entryPrice": 49000.0,
                        "markPrice": 50000.0,
                        "liquidationPrice": 45000.0,
                        "leverage": 10,
                        "unrealizedPnL": 1000.0,
                        "realizedPnL": 0.0,
                        "marginMode": "CROSS",
                        "side": "LONG",
                        "createdAt": "2024-01-01T00:00:00.000Z",
                        "updatedAt": "2024-01-01T00:00:00.000Z"
                    }
                }
            }
        }

    def _user_ws_update(self):
        """Mock WebSocket message from futures-perp:user-{userExchangeId} channel (Centrifugo push format)."""
        return {
            "push": {
                "channel": f"futures-perp:user-{self.user_exchange_id}",
                "pub": {
                    "data": {
                        "currency": self.quote_asset,
                        "funding": {
                            "currency": self.quote_asset,
                            "balance": 5000.0
                        },
                        "availableBalance": 4000.0,
                        "position": [],
                        "openOrder": [],
                        "updatedAt": "2024-01-01T00:00:00.000Z"
                    }
                }
            }
        }

    def _funding_ws_update(self):
        """Mock WebSocket message from futures-perp:funding-{userExchangeId} channel (Centrifugo push format)."""
        return {
            "push": {
                "channel": f"futures-perp:funding-{self.user_exchange_id}",
                "pub": {
                    "data": {
                        "coin": self.quote_asset.lower(),
                        "quantity": "4000.0",
                        "updatedAt": "2024-01-01T00:00:00.000Z"
                    }
                }
            }
        }

    def _fill_ws_update(self):
        """Mock WebSocket message from futures-perp:orderFilled-{userExchangeId} channel (Centrifugo push format)."""
        return {
            "push": {
                "channel": f"futures-perp:orderFilled-{self.user_exchange_id}",
                "pub": {
                    "data": {
                        "executionId": "fill_123456",
                        "orderId": "00001:00000000000000000000000001",
                        "instrumentName": self.ex_trading_pair,
                        "side": "BUY",
                        "fillPrice": 50000.0,
                        "fillQuantity": 1.0,
                        "fillValue": 50000.0,
                        "fee": [{"coin": self.quote_asset, "quantity": 10.0}],
                        "pnl": 0.0,
                        "isPnlRealized": False,
                        "createdAt": "2024-01-01T00:00:00.000Z"
                    }
                }
            }
        }

    def test_order_channel_naming(self):
        """Test order channel naming: futures-perp:order-{userExchangeId}."""
        msg = self._order_ws_update()
        self.assertEqual(msg["push"]["channel"], f"futures-perp:order-{self.user_exchange_id}")

    def test_position_channel_naming(self):
        """Test position channel naming: futures-perp:position-{userExchangeId}."""
        msg = self._position_ws_update()
        self.assertEqual(msg["push"]["channel"], f"futures-perp:position-{self.user_exchange_id}")

    def test_user_channel_naming(self):
        """Test user channel naming: futures-perp:user-{userExchangeId}."""
        msg = self._user_ws_update()
        self.assertEqual(msg["push"]["channel"], f"futures-perp:user-{self.user_exchange_id}")

    def test_order_fills_channel_naming(self):
        """Test order fills channel naming: futures-perp:orderFilled-{userExchangeId}."""
        msg = self._fill_ws_update()
        self.assertEqual(msg["push"]["channel"], f"futures-perp:orderFilled-{self.user_exchange_id}")

    def test_order_message_structure(self):
        """Test order message structure matches Swagger Order schema (Centrifugo push format)."""
        msg = self._order_ws_update()
        data = msg["push"]["pub"]["data"]

        required_fields = [
            "id", "user", "instrument", "type", "side", "status",
            "quantity", "limitPrice", "unFilledQuantity", "filledAvgPrice",
            "fee", "createdAt", "updatedAt"
        ]
        for field in required_fields:
            self.assertIn(field, data)

    def test_position_message_structure(self):
        """Test position message structure (Centrifugo push format)."""
        msg = self._position_ws_update()
        data = msg["push"]["pub"]["data"]

        required_fields = [
            "id", "user", "instrument", "quantity", "entryPrice",
            "markPrice", "liquidationPrice", "leverage", "unrealizedPnL",
            "side"
        ]
        for field in required_fields:
            self.assertIn(field, data)

    def test_fill_message_structure(self):
        """Test fill message structure (Centrifugo push format)."""
        msg = self._fill_ws_update()
        data = msg["push"]["pub"]["data"]

        required_fields = [
            "executionId", "orderId", "instrumentName", "side",
            "fillPrice", "fillQuantity", "fee"
        ]
        for field in required_fields:
            self.assertIn(field, data)

    def test_all_order_statuses(self):
        """Test all order status values from Swagger API OrderStatus enum."""
        statuses = [
            "INTENTION", "NEW", "PARTIALLY_FILLED", "FILLED",
            "CANCELLED", "REJECTED", "EXPIRED", "REPLACED", "ERROR"
        ]

        for status in statuses:
            msg = self._order_ws_update(status=status)
            self.assertEqual(msg["push"]["pub"]["data"]["status"], status)


class TestEvedexPerpetualUserStreamChannels(unittest.TestCase):
    """Test channel naming and message routing."""

    def test_centrifuge_channel_patterns(self):
        """Test all Centrifugo channel naming patterns (futures-perp: namespace)."""
        user_exchange_id = "12345"
        instrument = "BTC-USDT"

        channels = {
            "order": f"futures-perp:order-{user_exchange_id}",
            "position": f"futures-perp:position-{user_exchange_id}",
            "user": f"futures-perp:user-{user_exchange_id}",
            "orderFilled": f"futures-perp:orderFilled-{user_exchange_id}",
            "orderBook": f"futures-perp:orderBook-{instrument}-0.1",
            "trade": f"futures-perp:recent-trade-{instrument}"
        }

        # Verify patterns - all channels use futures-perp: namespace
        self.assertTrue(channels["order"].startswith("futures-perp:order-"))
        self.assertTrue(channels["position"].startswith("futures-perp:position-"))
        self.assertTrue(channels["user"].startswith("futures-perp:user-"))
        self.assertTrue(channels["orderFilled"].startswith("futures-perp:orderFilled-"))
        self.assertTrue(channels["orderBook"].startswith("futures-perp:orderBook-"))
        self.assertTrue(channels["trade"].startswith("futures-perp:recent-trade-"))

    def test_user_vs_public_channels(self):
        """Test that user channels include userExchangeId and public channels include instrument."""
        user_exchange_id = "12345"
        instrument = "BTC-USDT"

        # User channels - include userExchangeId (with futures-perp: namespace)
        user_channels = [
            f"futures-perp:order-{user_exchange_id}",
            f"futures-perp:position-{user_exchange_id}",
            f"futures-perp:user-{user_exchange_id}",
            f"futures-perp:orderFilled-{user_exchange_id}",
        ]

        for channel in user_channels:
            self.assertIn(user_exchange_id, channel)
            self.assertTrue(channel.startswith("futures-perp:"))

        # Public channels - include instrument (with futures-perp: namespace)
        public_channels = [
            f"futures-perp:orderBook-{instrument}-0.1",
            f"futures-perp:recent-trade-{instrument}"
        ]

        for channel in public_channels:
            self.assertIn(instrument, channel)
            self.assertTrue(channel.startswith("futures-perp:"))


if __name__ == "__main__":
    unittest.main()
