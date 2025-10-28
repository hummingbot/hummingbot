import asyncio
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import AsyncMock, patch

import ujson
from aioresponses.core import aioresponses

import hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.deepcoin_perpetual import deepcoin_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_auth import DeepcoinPerpetualAuth
from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_derivative import DeepcoinPerpetualDerivative
from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_user_stream_data_source import (
    DeepcoinPerpetualUserStreamDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class DeepcoinPerpetualUserStreamDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = CONSTANTS.TESTNET_DOMAIN

        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"
        cls.listen_key = "TEST_LISTEN_KEY"

    async def asyncSetUp(self) -> None:
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.emulated_time = 1640001112.223
        self.connector = DeepcoinPerpetualDerivative(
            binance_perpetual_api_key="", binance_perpetual_api_secret="", domain=self.domain, trading_pairs=[]
        )

        self.auth = DeepcoinPerpetualAuth(api_key=self.api_key, api_secret=self.secret_key, time_provider=self)
        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)
        api_factory = web_utils.build_api_factory(auth=self.auth)
        self.data_source = DeepcoinPerpetualUserStreamDataSource(
            auth=self.auth,
            domain=self.domain,
            api_factory=api_factory,
            connector=self.connector,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mock_done_event = asyncio.Event()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _mock_responses_done_callback(self, *_, **__):
        self.mock_done_event.set()

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _create_return_value_and_unlock_test_with_event(self, value):
        self.resume_test_event.set()
        return value

    def _successful_get_listen_key_response(self) -> str:
        resp = {"code": "0", "msg": "", "data": {"listenkey": self.listen_key, "expire_time": 1691403285}}
        return ujson.dumps(resp)

    def _simulate_user_update_event(self):
        # Order Trade Update
        resp = {
            "action": "PushTrade",
            "result": [
                {
                    "table": "Trade",
                    "data": {
                        "A": "36005550",
                        "CC": "USDT",
                        "D": "1",
                        "F": 0.026451,
                        "I": "BTCUSDT",
                        "IT": 1690804738,
                        "M": "36005550",
                        "OS": "1000175061255804",
                        "P": 29390,
                        "T": 29.39,
                        "TI": "1000168389225300",
                        "TT": 1690804738,
                        "V": 1,
                        "c": 0,
                        "f": "USDT",
                        "l": 125,
                        "m": "1",
                        "o": "0",
                    },
                }
            ],
        }
        return ujson.dumps(resp)

    @aioresponses()
    @patch(
        "hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_user_stream_data_source.DeepcoinPerpetualUserStreamDataSource._sleep"
    )
    async def test_get_listen_key_exception_raised(self, mock_api, _):
        url = web_utils.public_rest_url(path_url=CONSTANTS.USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, status=400, body=ujson.dumps(self._error_response()))

        with self.assertRaises(IOError):
            await self.data_source._get_listen_key()

    @aioresponses()
    async def test_get_listen_key_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_listen_key_response())

        result: str = await self.data_source._get_listen_key()

        self.assertEqual(self.listen_key, result)

    @aioresponses()
    async def test_ping_listen_key_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.USER_STREAM_EXTEND_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.put(regex_url, body=ujson.dumps({}))

        self.data_source._current_listen_key = self.listen_key
        result: bool = await self.data_source._ping_listen_key()
        self.assertTrue(result)

    @patch(
        "hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_user_stream_data_source.DeepcoinPerpetualUserStreamDataSource"
        "._ping_listen_key",
        new_callable=AsyncMock,
    )
    async def test_manage_listen_key_task_loop_keep_alive_failed(self, mock_ping_listen_key):
        mock_ping_listen_key.side_effect = lambda *args, **kwargs: self._create_return_value_and_unlock_test_with_event(
            False
        )

        self.data_source._current_listen_key = self.listen_key

        # Simulate LISTEN_KEY_KEEP_ALIVE_INTERVAL reached
        self.data_source._last_listen_key_ping_ts = 0

        self.listening_task = self.local_event_loop.create_task(self.data_source._manage_listen_key_task_loop())

        await self.resume_test_event.wait()

        # When ping fails, the exception is raised but the _current_listen_key is not reset
        # This is expected since the listen key management task will be restarted by the error handling
        self.assertEqual(None, self.data_source._current_listen_key)

    @aioresponses()
    async def test_manage_listen_key_task_loop_keep_alive_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.USER_STREAM_EXTEND_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.put(regex_url, body=ujson.dumps({}), callback=self._mock_responses_done_callback)

        self.data_source._current_listen_key = self.listen_key

        # Simulate LISTEN_KEY_KEEP_ALIVE_INTERVAL reached
        self.data_source._last_listen_key_ping_ts = 0

        self.listening_task = self.local_event_loop.create_task(self.data_source._manage_listen_key_task_loop())

        await self.mock_done_event.wait()

        self.assertGreater(self.data_source._last_listen_key_ping_ts, 0)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_successful(self, mock_api, mock_ws):
        url = web_utils.public_rest_url(path_url=CONSTANTS.USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_listen_key_response())

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._simulate_user_update_event())

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        msg = await msg_queue.get()
        self.assertTrue(msg, self._simulate_user_update_event)
        mock_ws.return_value.ping.assert_called()

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_api, mock_ws):
        url = web_utils.public_rest_url(path_url=CONSTANTS.USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_listen_key_response())

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    async def test_ensure_listen_key_task_running_with_no_task(self):
        # Test when there's no existing task
        self.assertIsNone(self.data_source._manage_listen_key_task)
        await self.data_source._ensure_listen_key_task_running()
        self.assertIsNotNone(self.data_source._manage_listen_key_task)

    @patch(
        "hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_user_stream_data_source.safe_ensure_future"
    )
    async def test_ensure_listen_key_task_running_with_running_task(self, mock_safe_ensure_future):
        # Test when task is already running - should return early (line 155)
        from unittest.mock import MagicMock

        mock_task = MagicMock()
        mock_task.done.return_value = False
        self.data_source._manage_listen_key_task = mock_task

        # Call the method
        await self.data_source._ensure_listen_key_task_running()

        # Should return early without creating a new task
        mock_safe_ensure_future.assert_not_called()
        self.assertEqual(mock_task, self.data_source._manage_listen_key_task)

    async def test_ensure_listen_key_task_running_with_done_task_cancelled_error(self):
        mock_task = AsyncMock()
        mock_task.done.return_value = True
        mock_task.side_effect = asyncio.CancelledError()
        self.data_source._manage_listen_key_task = mock_task

        await self.data_source._ensure_listen_key_task_running()

        # Task should be cancelled and replaced
        mock_task.cancel.assert_called_once()
        self.assertIsNotNone(self.data_source._manage_listen_key_task)
        self.assertNotEqual(mock_task, self.data_source._manage_listen_key_task)

    async def test_ensure_listen_key_task_running_with_done_task_exception(self):
        mock_task = AsyncMock()
        mock_task.done.return_value = True
        mock_task.side_effect = Exception("Test exception")
        self.data_source._manage_listen_key_task = mock_task

        await self.data_source._ensure_listen_key_task_running()

        # Task should be cancelled and replaced, exception should be ignored
        mock_task.cancel.assert_called_once()
        self.assertIsNotNone(self.data_source._manage_listen_key_task)
        self.assertNotEqual(mock_task, self.data_source._manage_listen_key_task)
