import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.connector.exchange.xt import xt_constants as CONSTANTS, xt_web_utils as web_utils
from hummingbot.connector.exchange.xt.xt_api_user_stream_data_source import XtAPIUserStreamDataSource
from hummingbot.connector.exchange.xt.xt_exchange import XtExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant


class XtAPIUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.connector = XtExchange(xt_api_key="test_api_key", xt_api_secret="test_secret_key", trading_pairs=["COINALPHA-HBOT"], trading_required=False)
        self.connector._time_synchronizer.add_time_offset_ms_sample(0)
        self.source = XtAPIUserStreamDataSource(self.connector.authenticator, ["COINALPHA-HBOT"], self.connector, self.connector._web_assistants_factory)
        self.network = NetworkMockingAssistant()
        await self.network.async_init()
        self.tasks = []

    async def asyncTearDown(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await super().asyncTearDown()

    def mock_token(self, mocked_api, token="listen-key"):
        mocked_api.post(web_utils.private_rest_url(CONSTANTS.WS_TOKEN_PATH_URL), payload={"rc": 0, "mc": "SUCCESS", "result": {"accessToken": token}})

    @aioresponses()
    async def test_get_listen_key_uses_authenticated_post(self, mocked_api):
        self.mock_token(mocked_api)
        self.assertEqual("listen-key", await self.source._get_listen_key())
        self.assertEqual("listen-key", self.source._current_listen_key)
        request = next(iter(mocked_api.requests.values()))[0]
        self.assertEqual("test_api_key", request.kwargs["headers"]["validate-appkey"])
        self.assertIn("validate-signature", request.kwargs["headers"])

    @aioresponses()
    async def test_invalid_token_response_raises(self, mocked_api):
        mocked_api.post(web_utils.private_rest_url(CONSTANTS.WS_TOKEN_PATH_URL), payload={"rc": 1, "mc": "AUTH_FAILED", "result": None})
        with self.assertRaises(IOError):
            await self.source._get_listen_key()
        self.assertIsNone(self.source._current_listen_key)

    @aioresponses()
    async def test_empty_token_is_rejected(self, mocked_api):
        self.mock_token(mocked_api, "")
        with self.assertRaises(IOError):
            await self.source._get_listen_key()

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_native_user_stream_subscribes_and_filters_control_frames(self, mocked_api, connect):
        self.mock_token(mocked_api)
        ws = self.network.create_websocket_mock()
        ws.closed = False
        connect.return_value = ws
        frames = ["pong", {"code": 0, "id": "1"}, {"topic": "unknown", "data": {}}, {"topic": "order"}, {"topic": "order", "data": {"i": "123", "s": "coinalpha_hbot"}}, {"topic": "trade", "data": {"i": "123", "t": "456"}}, {"topic": "balance", "data": {"a": "hbot", "f": "10"}}]
        for frame in frames:
            self.network.add_websocket_aiohttp_message(ws, frame if isinstance(frame, str) else json.dumps(frame))
        output = asyncio.Queue()
        task = asyncio.create_task(self.source.listen_for_user_stream(output))
        self.tasks.append(task)
        received = [await asyncio.wait_for(output.get(), 1) for _ in range(3)]
        self.assertEqual(frames[-3:], received)
        self.assertTrue(output.empty())
        self.assertEqual([{"method": "subscribe", "params": ["order", "trade", "balance"], "listenKey": "listen-key", "id": "1"}], self.network.json_messages_sent_through_websocket(ws))
        self.assertEqual(["ping"], self.network.text_messages_sent_through_websocket(ws))
        self.assertGreater(self.source.last_recv_time, 0)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.assertIsNone(self.source._current_listen_key)
        self.assertIsNone(self.source._ws_assistant)
        ws.close.assert_awaited()

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_invalid_listen_key_reconnects_with_fresh_token(self, mocked_api, connect):
        self.mock_token(mocked_api, "first-token")
        self.mock_token(mocked_api, "second-token")
        ws = self.network.create_websocket_mock()
        ws.closed = False
        connect.return_value = ws
        self.network.add_websocket_aiohttp_message(ws, json.dumps({"code": 2, "msg": "listenKey invalid"}))
        self.network.add_websocket_aiohttp_message(ws, json.dumps({"topic": "order", "data": {"i": "123"}}))
        output = asyncio.Queue()
        # Avoid the real ten-second token throttler window in a controlled reconnect test.
        token_limit = self.source._api_factory.throttler._id_to_limit_map[CONSTANTS.WS_TOKEN_PATH_URL]
        with patch.object(token_limit, "limit", 1000):
            task = asyncio.create_task(self.source.listen_for_user_stream(output))
            self.tasks.append(task)
            self.assertEqual("123", (await asyncio.wait_for(output.get(), 1))["data"]["i"])
        subscriptions = self.network.json_messages_sent_through_websocket(ws)
        self.assertEqual(["first-token", "second-token"], [request["listenKey"] for request in subscriptions])
        self.assertEqual(2, connect.call_count)

    async def test_periodic_token_renewal_uses_native_reconnect_path(self):
        self.source._listen_key_creation_time = 10
        with patch.object(self.source, "_time", return_value=10 + self.source.LISTEN_KEY_KEEP_ALIVE_INTERVAL):
            with self.assertRaises(ConnectionError):
                await self.source._process_websocket_messages(AsyncMock(), asyncio.Queue())

    async def test_subscription_error_raises(self):
        with self.assertRaises(IOError):
            await self.source._process_event_message({"code": 1, "msg": "invalid topic"}, asyncio.Queue())

    async def test_connection_and_subscription_errors_use_native_cleanup(self):
        ws = AsyncMock()
        with patch.object(self.source, "_connected_websocket_assistant", return_value=ws), patch.object(self.source, "_subscribe_channels", side_effect=IOError("subscription failed")), patch.object(self.source, "_sleep", side_effect=asyncio.CancelledError) as sleep:
            with self.assertRaises(asyncio.CancelledError):
                await self.source.listen_for_user_stream(asyncio.Queue())
        sleep.assert_awaited_once()
        ws.disconnect.assert_awaited_once()

    async def test_subscription_cancellation_propagates(self):
        with patch.object(self.source, "_get_listen_key", side_effect=asyncio.CancelledError):
            with self.assertRaises(asyncio.CancelledError):
                await self.source._subscribe_channels(AsyncMock())

    async def test_connection_cancellation_propagates(self):
        with patch.object(self.source, "_connected_websocket_assistant", side_effect=asyncio.CancelledError):
            with self.assertRaises(asyncio.CancelledError):
                await self.source.listen_for_user_stream(asyncio.Queue())

    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._process_websocket_messages", new_callable=AsyncMock)
    async def test_heartbeat_send_failure_reaches_native_reconnect_loop(self, process):
        self.source._listen_key_creation_time = self.source._time()
        process.side_effect = asyncio.TimeoutError
        ws = AsyncMock()
        ws.send.side_effect = IOError("send failed")
        with self.assertRaises(IOError):
            await self.source._process_websocket_messages(ws, asyncio.Queue())
        self.assertEqual("ping", ws.send.call_args.args[0].payload)

    async def test_stop_disconnects_and_clears_token(self):
        ws = AsyncMock()
        self.source._ws_assistant = ws
        self.source._current_listen_key = "listen-key"
        await self.source.stop()
        ws.disconnect.assert_awaited_once()
        self.assertIsNone(self.source._current_listen_key)
        self.assertIsNone(self.source._ws_assistant)

    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._process_websocket_messages", new_callable=AsyncMock)
    async def test_processing_returns_when_native_stream_ends(self, process):
        self.source._listen_key_creation_time = self.source._time()
        await asyncio.wait_for(self.source._process_websocket_messages(AsyncMock(), asyncio.Queue()), 1)
        process.assert_awaited_once()
