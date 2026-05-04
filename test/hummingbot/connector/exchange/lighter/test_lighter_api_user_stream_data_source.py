import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.lighter.lighter_api_user_stream_data_source import LighterAPIUserStreamDataSource
from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth


class LighterAPIUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.connector = MagicMock()
        self.connector.rest_api_key = "api-key"
        self.connector.account_index = ""
        self.connector.api_key_index = ""
        self.connector._get_lighter_auth_token = MagicMock(return_value="ws-auth-token")
        self.auth = LighterAuth(api_key="api-key", account_identifier="123")
        self.data_source = LighterAPIUserStreamDataSource(
            connector=self.connector,
            api_factory=MagicMock(),
            auth=self.auth,
        )

    async def test_connected_websocket_assistant_connects_with_api_key_header(self):
        ws = MagicMock()
        ws.connect = AsyncMock()
        self.data_source._api_factory.get_ws_assistant = AsyncMock(return_value=ws)

        connected_ws = await self.data_source._connected_websocket_assistant()

        self.assertIs(ws, connected_ws)
        ws.connect.assert_awaited_once_with(
            ws_url="wss://mainnet.zklighter.elliot.ai/stream",
            ws_headers={"X-Api-Key": "api-key"},
            ping_timeout=30,
        )

    async def test_subscribe_channels_sends_spot_private_channels_with_compatibility_variants(self):
        """Spot connector subscribes to private channels using both delimiter variants."""
        ws = MagicMock()
        ws.send = AsyncMock()
        ws.receive = AsyncMock(return_value=MagicMock(data={"type": "connected"}))
        self.connector.account_index = "321"
        self.connector.api_key_index = "9"

        await self.data_source._subscribe_channels(ws)

        # 3 identifiers (123, 321, 9) × 4 channels × 2 delimiters = 24 subscriptions
        self.assertEqual(24, ws.send.await_count)
        sent_payloads = [call.args[0].payload for call in ws.send.await_args_list]
        # Slash format is preferred first; colon fallback is still sent.
        self.assertEqual("account_all/123", sent_payloads[0]["channel"])
        sent_channels = [payload["channel"] for payload in sent_payloads]
        self.assertIn("account_all:123", sent_channels)
        self.assertIn("account_all/123", sent_channels)
        self.assertIn("account_all:321", sent_channels)
        self.assertIn("account_all/321", sent_channels)
        self.assertIn("account_all:9", sent_channels)
        self.assertIn("account_all/9", sent_channels)
        self.assertIn("account_all_assets:123", sent_channels)
        self.assertIn("account_all_assets/123", sent_channels)
        self.assertIn("account_all_assets:321", sent_channels)
        self.assertIn("account_all_assets/321", sent_channels)
        self.assertIn("account_all_assets:9", sent_channels)
        self.assertIn("account_all_assets/9", sent_channels)
        self.assertIn("account_all_orders:123", sent_channels)
        self.assertIn("account_all_orders/123", sent_channels)
        self.assertIn("account_all_orders:321", sent_channels)
        self.assertIn("account_all_orders/321", sent_channels)
        self.assertIn("account_all_orders:9", sent_channels)
        self.assertIn("account_all_orders/9", sent_channels)
        self.assertIn("account_all_trades:123", sent_channels)
        self.assertIn("account_all_trades/123", sent_channels)
        self.assertIn("account_all_trades:321", sent_channels)
        self.assertIn("account_all_trades/321", sent_channels)
        self.assertIn("account_all_trades:9", sent_channels)
        self.assertIn("account_all_trades/9", sent_channels)
        assets_and_orders_payloads = {
            payload["channel"]: payload for payload in sent_payloads
            if (
                payload["channel"].startswith("account_all_assets:")
                or payload["channel"].startswith("account_all_orders:")
                or payload["channel"].startswith("account_all_assets/")
                or payload["channel"].startswith("account_all_orders/")
            )
        }
        self.assertTrue(all(payload.get("auth") == "ws-auth-token" for payload in assets_and_orders_payloads.values()))
        # account_all and account_all_trades do NOT require an auth token
        non_auth_payloads = {
            payload["channel"]: payload for payload in sent_payloads
            if (
                payload["channel"].startswith("account_all:")
                or payload["channel"].startswith("account_all_trades:")
                or payload["channel"].startswith("account_all/")
                or payload["channel"].startswith("account_all_trades/")
            )
        }
        self.assertTrue(all("auth" not in payload for payload in non_auth_payloads.values()))
        # Unsupported channels must NOT appear
        for channel in sent_channels:
            self.assertNotIn("account_positions", channel)
            self.assertNotIn("account_info", channel)
            self.assertNotIn("account_order_updates", channel)
            self.assertNotIn("account_trades:", channel)
            self.assertNotIn("account_trades/", channel)

    async def test_subscribe_channels_deduplicates_identical_identifiers(self):
        """When account_index equals the auth public key, each channel is only sent once."""
        ws = MagicMock()
        ws.send = AsyncMock()
        ws.receive = AsyncMock(return_value=MagicMock(data={"type": "connected"}))
        self.connector.account_index = "123"  # same as user_wallet_public_key
        self.connector.api_key_index = ""

        await self.data_source._subscribe_channels(ws)

        # Only 1 unique identifier → 4 channels × 2 delimiters = 8 sends
        self.assertEqual(8, ws.send.await_count)

    async def test_subscribe_channels_raises_when_not_connected(self):
        ws = MagicMock()
        ws.receive = AsyncMock(return_value=MagicMock(data={"type": "error"}))

        with self.assertRaises(IOError):
            await self.data_source._subscribe_channels(ws)

    async def test_process_websocket_messages_replies_to_ping_and_processes_events(self):
        websocket_assistant = MagicMock()
        websocket_assistant.send = AsyncMock()
        queue = asyncio.Queue()

        async def iter_messages():
            yield MagicMock(data={"type": "ping"})
            yield MagicMock(data={"type": "update/account_all", "channel": "account_all:123", "data": {}})

        websocket_assistant.iter_messages = iter_messages
        self.data_source._process_event_message = AsyncMock()

        await self.data_source._process_websocket_messages(websocket_assistant, queue)

        websocket_assistant.send.assert_awaited_once()
        self.data_source._process_event_message.assert_awaited_once_with(
            event_message={"type": "update/account_all", "channel": "account_all:123", "data": {}},
            queue=queue,
        )

    async def test_process_event_message_enqueues_account_messages(self):
        queue = asyncio.Queue()
        message = {"type": "update/account_all", "channel": "account_all:123", "account": {"assets": []}}

        await self.data_source._process_event_message(message, queue)

        queued = queue.get_nowait()
        self.assertEqual(message, queued)

    async def test_process_event_message_routes_account_all_assets_messages(self):
        queue = asyncio.Queue()
        assets_message = {"type": "update/account_all_assets", "channel": "account_all_assets:123", "data": {"assets": {}}}

        await self.data_source._process_event_message(assets_message, queue)

        self.assertFalse(queue.empty())
        self.assertEqual(assets_message, queue.get_nowait())

    async def test_process_event_message_ignores_unknown_messages(self):
        queue = asyncio.Queue()

        await self.data_source._process_event_message({"type": "other", "channel": "other:123"}, queue)

        self.assertTrue(queue.empty())

    async def test_process_event_message_raises_on_websocket_error(self):
        queue = asyncio.Queue()

        with self.assertRaises(IOError):
            await self.data_source._process_event_message(
                {"error": {"message": "invalid auth"}},
                queue,
            )

    async def test_process_event_message_ignores_invalid_channel_error(self):
        """'Invalid Channel' responses must be silently swallowed, not crash the stream."""
        queue = asyncio.Queue()
        await self.data_source._process_event_message(
            {"error": {"message": "Invalid Channel"}},
            queue,
        )
        self.assertTrue(queue.empty())

    async def test_connected_websocket_assistant_omits_api_key_header_when_missing(self):
        ws = MagicMock()
        ws.connect = AsyncMock()
        self.connector.rest_api_key = ""
        self.data_source._api_factory.get_ws_assistant = AsyncMock(return_value=ws)

        await self.data_source._connected_websocket_assistant()

        ws.connect.assert_awaited_once_with(
            ws_url="wss://mainnet.zklighter.elliot.ai/stream",
            ws_headers={},
            ping_timeout=30,
        )

    async def test_subscribe_channels_without_auth_token_skips_auth_fields(self):
        ws = MagicMock()
        ws.send = AsyncMock()
        ws.receive = AsyncMock(return_value=MagicMock(data={"type": "connected"}))
        self.connector.account_index = "321"
        self.connector.api_key_index = "9"
        self.connector._get_lighter_auth_token = MagicMock(side_effect=RuntimeError("no token"))

        await self.data_source._subscribe_channels(ws)

        sent_payloads = [call.args[0].payload for call in ws.send.await_args_list]
        auth_channels = [
            payload for payload in sent_payloads
            if payload["channel"].startswith("account_all_assets") or payload["channel"].startswith("account_all_orders")
        ]
        self.assertTrue(all("auth" not in payload for payload in auth_channels))

    async def test_listen_for_user_stream_logs_close_levels(self):
        logger = MagicMock()
        self.data_source.logger = MagicMock(return_value=logger)
        self.data_source._on_user_stream_interruption = AsyncMock()
        self.data_source._connected_websocket_assistant = AsyncMock(side_effect=[ConnectionError("close code = 1000"), asyncio.CancelledError()])

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(asyncio.Queue())

        logger.debug.assert_called_once()

        logger.reset_mock()
        self.data_source._connected_websocket_assistant = AsyncMock(side_effect=[ConnectionError("close code = 1006"), asyncio.CancelledError()])

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(asyncio.Queue())

        logger.warning.assert_called_once()

    async def test_listen_for_user_stream_suppresses_repeated_errors(self):
        logger = MagicMock()
        self.data_source.logger = MagicMock(return_value=logger)
        self.data_source._on_user_stream_interruption = AsyncMock()
        self.data_source._sleep = AsyncMock()
        self.data_source._connected_websocket_assistant = AsyncMock(side_effect=[RuntimeError("boom-1"), RuntimeError("boom-2"), asyncio.CancelledError()])

        with patch(
            "hummingbot.connector.exchange.lighter.lighter_api_user_stream_data_source.time.time",
            side_effect=[100.0, 110.0],
        ):
            with self.assertRaises(asyncio.CancelledError):
                await self.data_source.listen_for_user_stream(asyncio.Queue())

        logger.exception.assert_called_once()
        logger.debug.assert_called_once()

    async def test_listen_for_user_stream_calls_subscribe_ping_and_process(self):
        """Success path: subscribe, ping, then process are all called (lines 41-43)."""
        logger = MagicMock()
        self.data_source.logger = MagicMock(return_value=logger)
        self.data_source._on_user_stream_interruption = AsyncMock()
        mock_ws = MagicMock()
        self.data_source._connected_websocket_assistant = AsyncMock(return_value=mock_ws)
        self.data_source._subscribe_channels = AsyncMock()
        self.data_source._send_ping = AsyncMock()
        self.data_source._process_websocket_messages = AsyncMock(side_effect=asyncio.CancelledError())

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(asyncio.Queue())

        self.data_source._subscribe_channels.assert_awaited_once_with(websocket_assistant=mock_ws)
        self.data_source._send_ping.assert_awaited_once_with(websocket_assistant=mock_ws)
