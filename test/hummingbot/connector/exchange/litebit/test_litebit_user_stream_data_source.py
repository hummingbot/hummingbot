import asyncio
import json
from typing import Awaitable, Optional
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.litebit import litebit_constants as CONSTANTS
from hummingbot.connector.exchange.litebit.litebit_api_user_stream_data_source import LitebitAPIUserStreamDataSource
from hummingbot.connector.exchange.litebit.litebit_auth import LitebitAuth
from hummingbot.connector.exchange.litebit.litebit_exchange import LitebitExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class LitebitUserStreamDataSourceUnitTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)

        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        self.auth = LitebitAuth(
            api_key="TEST_API_KEY",
            secret_key="TEST_SECRET",
            time_provider=mock_time_provider)

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = LitebitExchange(
            client_config_map=client_config_map,
            litebit_api_key="",
            litebit_secret_key="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = LitebitAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(
            bidict({self.trading_pair: self.trading_pair}))

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
    def test_listen_for_user_stream_subscribes_to_orders_and_fill_events(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe = {
            "rid": "subscribe",
            "event": "subscribe"}

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe))

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value, timeout=5)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_messages))
        expected_login = {
            "rid": "authenticate",
            "event": "authenticate",
            "data": {
                "api_key": self.auth.api_key,
                "signature": "23408698e0c8b6afb6e9ced0a0e7c8173124c1fe0c0e7354e2692c1e12784fa2",  # noqa: mock
                "timestamp": int(self.auth.time_provider.time.return_value * 1e3),
            }
        }
        self.assertEqual(expected_login, sent_messages[0])
        expected_subscription = {
            "rid": "subscribe",
            "event": "subscribe",
            "data": ["fills", "orders"],
        }
        self.assertEqual(expected_subscription, sent_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to private fills and orders channels..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_authentication_failure(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        login_response = {
            "rid": "authenticate",
            "event": "error",
            "data": {
                "code": 0,
                "message": ""
            },
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(login_response))

        output_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value, timeout=5)

        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error while listening to user stream. Retrying after 5 seconds..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        successful_login_response = {
            "rid": "authenticate",
            "event": "authenticate",
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value,
            json.dumps(successful_login_response))
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value, timeout=5)

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
    def test_only_events_with_order_or_fills_channel_are_queued(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe = {"rid": "subscribe", "event": "subscribe"}
        event_with_invalid_channel = {"event": "candle", "data": {"market": "BTC-EUR", "interval": 900,
                                                                  "ohlcv": [1525337100, "0.1221", "0.1460", "0.1032",
                                                                            "0.1538", "5.305"]}}
        fill_event = {"event": "fill", "data": {"uuid": "234234897234-1243-1234-qsf234",
                                                "order_uuid": "234234897234-1243-1234-qsf235", "amount": "0.00100000",
                                                "price": "42986.64",
                                                "amount_quote": "43.09410660", "side": "buy", "fee": "0.10746660",
                                                "market": "BTC-EUR",
                                                "liquidity": "taker",
                                                "timestamp": 1622123573863
                                                }
                      }
        orders_event = {
            "event": "order",
            "data": {
                "uuid": "5f7bda37-5dac-4525-bd72-14df3fbc6f82",
                "amount": "1.00000000",
                "amount_filled": "0.00000000",
                "amount_quote": None,
                "amount_quote_filled": "0.00000000",
                "fee": "0.00000000",
                "price": "0.01635866",
                "side": "buy",
                "type": "limit",
                "status": "open",
                "filled_status": "not_filled",
                "cancel_status": None,
                "stop": None,
                "stop_price": None,
                "post_only": False,
                "time_in_force": "gtc",
                "created_at": 1614919085000,
                "updated_at": 1614919085000,
                "expire_at": None,
                "market": "BTC-EUR",
                "client_id": None
            }
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe))
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

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value, timeout=5)

        self.assertEqual(2, output_queue.qsize())
        queued_event = output_queue.get_nowait()
        self.assertEqual(fill_event, queued_event)
        queued_event = output_queue.get_nowait()
        self.assertEqual(orders_event, queued_event)
