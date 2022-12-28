import asyncio
import json
import re
from typing import Awaitable, Optional
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS, ascend_ex_web_utils as web_utils
from hummingbot.connector.exchange.ascend_ex.ascend_ex_api_user_stream_data_source import (
    AscendExAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.ascend_ex.ascend_ex_auth import AscendExAuth
from hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange import AscendExExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class AscendExUserStreamTrackerTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "com"

        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000
        self.auth = AscendExAuth(api_key="TEST_API_KEY", secret_key="TEST_SECRET")

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = AscendExExchange(
            client_config_map=client_config_map,
            ascend_ex_api_key="",
            ascend_ex_secret_key="",
            ascend_ex_group_id="",
            trading_pairs=[],
            trading_required=False,
        )
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = AscendExAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def get_listen_key_mock():
        listen_key = {"data": {"accountGroup": 6}}
        return listen_key

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_subscribes_to_orders_and_balances_events(self, mock_api, ws_connect_mock):
        url = web_utils.public_rest_url(path_url=CONSTANTS.INFO_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self.get_listen_key_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {}

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(result_subscribe_trades)
        )

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(1, len(sent_subscription_messages))
        expected_orders_subscription = {"op": "sub", "ch": "order:cash"}
        self.assertEqual(expected_orders_subscription, sent_subscription_messages[0])

        self.assertTrue(self._is_logged("INFO", "Subscribed to private order changes and balance updates channels..."))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_get_listen_key_successful_with_user_update_event(self, mock_api, mock_ws):
        url = web_utils.public_rest_url(path_url=CONSTANTS.INFO_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self.get_listen_key_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        order_event = {
            "m": "order",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "ac": "CASH",
            "data": {
                "s": "BTC/USDT",
                "sn": 8159711,
                "sd": "Buy",
                "ap": "0",
                "bab": "2006.5974027",
                "btb": "2006.5974027",
                "cf": "0",
                "cfq": "0",
                "err": "",
                "fa": "USDT",
                "orderId": "s16ef210b1a50866943712bfaf1584b",
                "ot": "Market",
                "p": "7967.62",
                "q": "0.0083",
                "qab": "793.23",
                "qtb": "860.23",
                "sp": "",
                "st": "New",
                "t": 1576019215402,
                "ei": "NULL_VAL",
            },
        }
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, json.dumps(order_event))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        msg = self.async_run_with_timeout(msg_queue.get())
        self.assertEqual(order_event, msg)
        mock_ws.return_value.ping.assert_called()

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_ping_payload(self, mock_api, mock_ws):
        url = web_utils.public_rest_url(path_url=CONSTANTS.INFO_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self.get_listen_key_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        mock_ping = {"op": "ping"}

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, json.dumps(mock_ping))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.exchange.ascend_ex.ascend_ex_api_user_stream_data_source.AscendExAPIUserStreamDataSource"
        "._sleep"
    )
    def test_listen_for_user_stream_connection_failed(self, mock_api, sleep_mock, mock_ws):
        url = web_utils.public_rest_url(path_url=CONSTANTS.INFO_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self.get_listen_key_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        mock_ws.side_effect = Exception("TEST ERROR")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        msg_queue = asyncio.Queue()
        try:
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(msg_queue))
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.exchange.ascend_ex.ascend_ex_api_user_stream_data_source.AscendExAPIUserStreamDataSource"
        "._sleep"
    )
    def test_listen_for_user_stream_iter_message_throws_exception(self, mock_api, sleep_mock, mock_ws):
        url = web_utils.public_rest_url(path_url=CONSTANTS.INFO_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self.get_listen_key_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = Exception("TEST ERROR")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        try:
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(msg_queue))
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."))
