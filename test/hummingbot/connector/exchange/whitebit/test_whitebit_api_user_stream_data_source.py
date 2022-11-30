import asyncio
import json
from typing import Awaitable, Optional
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.whitebit import whitebit_constants as CONSTANTS, whitebit_web_utils as web_utils
from hummingbot.connector.exchange.whitebit.whitebit_api_user_stream_data_source import WhitebitAPIUserStreamDataSource
from hummingbot.connector.exchange.whitebit.whitebit_auth import WhitebitAuth
from hummingbot.connector.exchange.whitebit.whitebit_exchange import WhitebitExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant


class WhitebitAPIUserStreamDataSourceTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.trading_pair.replace("-", "_")
        cls.api_key = "someKey"
        cls.api_secret_key = "someSecretKey"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = web_utils.create_throttler()
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000
        self.auth = WhitebitAuth(self.api_key, self.api_secret_key, time_provider=self.mock_time_provider)

        self.api_factory = web_utils.build_api_factory()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = WhitebitExchange(
            client_config_map=client_config_map,
            whitebit_api_key="",
            whitebit_secret_key="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )

        self.data_source = WhitebitAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

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

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_subscribes_to_orders_trades_and_balances_events(self, mock_api, ws_connect_mock):
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_WS_AUTHENTICATION_TOKEN_PATH)

        resp = {"websocket_token": "test_token"}
        mock_api.post(url, body=json.dumps(resp))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_auth = {"id": 0, "result": {"status": "success"}, "error": None}
        result_subscribe_balances = {"id": 1, "result": {"status": "success"}, "error": None}
        result_subscribe_trades = {"id": 2, "result": {"status": "success"}, "error": None}
        result_subscribe_orders = {"id": 3, "result": {"status": "success"}, "error": None}

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(result_auth)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(result_subscribe_balances)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(result_subscribe_trades)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(result_subscribe_orders)
        )

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_auth_message, *sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        expected_auth_message = {"id": 0, "method": "authorize", "params": ["test_token", "public"]}
        self.assertEqual(expected_auth_message, sent_auth_message)

        self.assertEqual(3, len(sent_subscription_messages))

        expected_balances_subscription = {
            "id": 1,
            "method": "balanceSpot_subscribe",
            "params": self.ex_trading_pair.split("_"),
        }
        self.assertEqual(expected_balances_subscription, sent_subscription_messages[0])

        expected_trades_subscription = {"id": 2, "method": "deals_subscribe", "params": [[self.ex_trading_pair]]}
        self.assertEqual(expected_trades_subscription, sent_subscription_messages[1])

        expected_orders_subscription = {"id": 3, "method": "ordersPending_subscribe", "params": [self.ex_trading_pair]}
        self.assertEqual(expected_orders_subscription, sent_subscription_messages[2])

        self.assertTrue(self._is_logged("INFO", "Subscribed to private order changes and balance updates channels..."))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_logs_error_when_auth_token_request_fails(self, mock_api, ws_connect_mock):
        request_event = asyncio.Event()
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_WS_AUTHENTICATION_TOKEN_PATH)

        resp = {"error": "errorMessage"}
        mock_api.post(url, body=json.dumps(resp), status=404, callback=lambda *args, **kwargs: request_event.set())

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        output_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.async_run_with_timeout(request_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds...",
            )
        )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_logs_error_when_authentication_fails(self, mock_api, ws_connect_mock):
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_WS_AUTHENTICATION_TOKEN_PATH)

        resp = {"websocket_token": "test_token"}
        mock_api.post(url, body=json.dumps(resp))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_auth = {"id": 0, "result": {"status": "error"}, "error": "Invalid token"}

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(result_auth)
        )

        output_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged("ERROR", "Error authenticating the private websocket connection"))
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds...",
            )
        )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_accepts_only_balance_trades_and_orders_event_messages(
        self, mock_api, ws_connect_mock
    ):
        url = web_utils.private_rest_url(path_url=CONSTANTS.WHITEBIT_WS_AUTHENTICATION_TOKEN_PATH)

        resp = {"websocket_token": "test_token"}
        mock_api.post(url, body=json.dumps(resp))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_auth = {"id": 0, "result": {"status": "success"}, "error": None}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(result_auth)
        )

        invalid_event = {
            "id": None,
            "method": "invalid_method",
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(invalid_event)
        )

        balance_event = {
            "id": None,
            "method": CONSTANTS.WHITEBIT_WS_PRIVATE_BALANCE_CHANNEL,
            "params": [
                {"USDT": {"available": "100.1885", "freeze": "0"}},
            ],
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(balance_event)
        )

        trade_event = {
            "id": None,
            "method": CONSTANTS.WHITEBIT_WS_PRIVATE_TRADES_CHANNEL,
            "params": [
                252104486,
                1602770801.015587,
                "BTC_USDT",
                7425988844,
                "11399.24",
                "0.008256",
                "0.094112125440",
                "1234",
            ],
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(trade_event)
        )

        order_event = {
            "id": None,
            "method": CONSTANTS.WHITEBIT_WS_PRIVATE_ORDERS_CHANNEL,
            "params": [
                2,
                {
                    "id": 621879,
                    "market": "BTC_USDT",
                    "type": 1,
                    "side": 1,
                    "ctime": 1601475234.656275,
                    "mtime": 1601475266.733574,
                    "price": "10646.12",
                    "amount": "0.01",
                    "left": "0.008026",
                    "deal_stock": "0.001974",
                    "deal_money": "21.01544088",
                    "deal_fee": "2.101544088",
                    "client_order_id": "22",
                },
            ],
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(order_event)
        )

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(3, msg_queue.qsize())
        received_event = msg_queue.get_nowait()
        self.assertEqual(balance_event, received_event)
        received_event = msg_queue.get_nowait()
        self.assertEqual(trade_event, received_event)
        received_event = msg_queue.get_nowait()
        self.assertEqual(order_event, received_event)

    def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(self._is_logged("ERROR", "Unexpected error occurred subscribing to user streams..."))
