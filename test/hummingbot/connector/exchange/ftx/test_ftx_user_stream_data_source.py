import asyncio
import json
from typing import Awaitable, Optional
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from aiohttp import WSMessage, WSMsgType
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.ftx import ftx_constants as CONSTANTS
from hummingbot.connector.exchange.ftx.ftx_api_user_stream_data_source import FtxAPIUserStreamDataSource
from hummingbot.connector.exchange.ftx.ftx_auth import FtxAuth
from hummingbot.connector.exchange.ftx.ftx_exchange import FtxExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class FtxUserStreamDataSourceUnitTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.trading_pair.replace("-", "/")

        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)

        self.auth = FtxAuth(
            api_key="TEST_API_KEY",
            secret_key="TEST_SECRET")

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = FtxExchange(
            client_config_map=client_config_map,
            ftx_api_key="",
            ftx_secret_key="",
            ftx_subaccount_name="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = FtxAPIUserStreamDataSource(
            auth=self.auth,
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}/{self.quote_asset}": self.trading_pair}))

        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.ftx.ftx_auth.FtxAuth._time")
    def test_listen_for_user_stream_subscribes_to_orders_and_fill_events(self, time_mock, ws_connect_mock):
        time_mock.return_value = 1540001112.223334
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_fills = {
            "type": "subscribed",
            "channel": "fills"}
        result_subscribe_orders = {
            "type": "subscribed",
            "channel": "orders"}

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_fills))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_orders))

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(3, len(sent_messages))
        expected_login = {
            "op": "login",
            "args": {
                "key": self.auth.api_key,
                "sign": "21558c223bca797af1bf01672fcaabcba28e000a6c0b4784d15ff1c0ab0dda17",  # noqa: mock
                "time": int(time_mock.return_value * 1e3),
            }
        }
        self.assertEqual(expected_login, sent_messages[0])
        expected_fills_subscription = {
            "op": "subscribe",
            "channel": "fills",
        }
        self.assertEqual(expected_fills_subscription, sent_messages[1])
        expected_orders_subscription = {
            "op": "subscribe",
            "channel": "orders",
        }
        self.assertEqual(expected_orders_subscription, sent_messages[2])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to private fills and orders channels..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_authentication_failure(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        login_response = {
            "type": CONSTANTS.WS_EVENT_ERROR_TYPE,
            "code": CONSTANTS.WS_EVENT_ERROR_CODE,
            "msg": CONSTANTS.WS_EVENT_INVALID_LOGIN_MESSAGE,
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(login_response))

        output_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error while listening to user stream. Retrying after 5 seconds..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        successful_login_response = {
            "event": "login",
            "code": "0",
            "msg": ""
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value,
            json.dumps(successful_login_response))
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    def test_listen_for_user_stream_connection_failed(self, sleep_mock, mock_ws):
        sleep_mock.side_effect = asyncio.CancelledError
        mock_ws.side_effect = Exception("TEST ERROR.")

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_sends_ping_message_before_ping_interval_finishes(
            self,
            ws_connect_mock):

        successful_login_response = {
            "event": "login",
            "code": "0",
            "msg": ""
        }

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = [
            WSMessage(type=WSMsgType.TEXT, data=json.dumps(successful_login_response), extra=None),
            asyncio.TimeoutError("Test timeout"),
            asyncio.CancelledError]

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        try:
            self.async_run_with_timeout(self.listening_task, timeout=10)
        except asyncio.CancelledError:
            pass

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        expected_ping_message = {"op": "ping"}
        self.assertEqual(expected_ping_message, sent_messages[-1])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_only_events_with_order_or_fills_channel_are_queued(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_fills = {
            "type": "subscribed",
            "channel": "fills"}
        result_subscribe_orders = {
            "type": "subscribed",
            "channel": "orders"}
        event_with_invalid_channel = {
            "channel": "unknown",
            "type": "update"
        }
        fill_event = {
            "channel": CONSTANTS.WS_PRIVATE_FILLS_CHANNEL,
            "data": {
                "fee": 78.05799225,
                "feeRate": 0.0014,
                "future": "BTC-PERP",
                "id": 7828307,
                "liquidity": "taker",
                "market": "BTC-PERP",
                "orderId": 38065410,
                "tradeId": 19129310,
                "price": 3723.75,
                "side": "buy",
                "size": 14.973,
                "time": "2019-05-07T16:40:58.358438+00:00",
                "type": "order"
            },
            "type": "update"
        }
        orders_event = {
            "channel": CONSTANTS.WS_PRIVATE_ORDERS_CHANNEL,
            "data": {
                "id": 24852229,
                "clientId": None,
                "market": "XRP-PERP",
                "type": "limit",
                "side": "buy",
                "size": 42353.0,
                "price": 0.2977,
                "reduceOnly": False,
                "ioc": False,
                "postOnly": False,
                "status": "closed",
                "filledSize": 42353.0,
                "remainingSize": 0.0,
                "avgFillPrice": 0.2978,
                "createdAt": "2021-05-02T22:40:07.217963+00:00"
            },
            "type": "update"
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_fills))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_orders))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(event_with_invalid_channel))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(fill_event))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(orders_event))

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(2, output_queue.qsize())
        queued_event = output_queue.get_nowait()
        self.assertEqual(fill_event, queued_event)
        queued_event = output_queue.get_nowait()
        self.assertEqual(orders_event, queued_event)
