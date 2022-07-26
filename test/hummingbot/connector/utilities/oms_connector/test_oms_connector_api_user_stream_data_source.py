import asyncio
import hashlib
import hmac
import json
import unittest
from typing import Any, Awaitable, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import WSMessage, WSMsgType

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utilities.oms_connector import oms_connector_constants as CONSTANTS
from hummingbot.connector.utilities.oms_connector.oms_connector_api_user_stream_data_source import (
    OMSConnectorAPIUserStreamDataSource,
)
from hummingbot.connector.utilities.oms_connector.oms_connector_auth import OMSConnectorAuth
from hummingbot.connector.utilities.oms_connector.oms_connector_web_utils import (
    OMSConnectorURLCreatorBase,
    build_api_factory,
)


class TestURLCreator(OMSConnectorURLCreatorBase):
    def get_rest_url(self, path_url: str) -> str:
        return "https://some.url"

    def get_ws_url(self) -> str:
        return "wss://some.url"


class OMSConnectorUserStreamDataSourceTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.api_key = "someApiKey"
        cls.secret = "someSecret"
        cls.user_id = 20
        cls.time_mock = 1655283229.419752
        cls.nonce = str(int(cls.time_mock * 1e3))
        auth_concat = f"{cls.nonce}{cls.user_id}{cls.api_key}"
        cls.signature = hmac.new(
            key=cls.secret.encode("utf-8"),
            msg=auth_concat.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        cls.user_name = "someUserName"
        cls.oms_id = 1
        cls.account_id = 3

    @patch("hummingbot.core.utils.tracking_nonce.NonceCreator._time")
    def setUp(self, time_mock: MagicMock) -> None:
        super().setUp()
        time_mock.return_value = self.time_mock
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.auth = OMSConnectorAuth(api_key=self.api_key, secret_key=self.secret, user_id=self.user_id)
        self.initialize_auth()
        api_factory = build_api_factory(auth=self.auth)
        url_provider = TestURLCreator()

        self.data_source = OMSConnectorAPIUserStreamDataSource(
            api_factory=api_factory, url_provider=url_provider, oms_id=self.oms_id
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
        return any(
            record.levelname == log_level
            and record.getMessage() == message
            for record in self.log_records
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def initialize_auth(self):
        auth_resp = self.get_auth_success_response()
        self.auth.update_with_rest_response(auth_resp)

    def get_auth_success_response(self) -> Dict[str, Any]:
        auth_resp = {
            "Authenticated": True,
            "SessionToken": "0e8bbcbc-6ada-482a-a9b4-5d9218ada3f9",
            "User": {
                "UserId": self.user_id,
                "UserName": self.user_name,
                "Email": "",
                "EmailVerified": True,
                "AccountId": self.account_id,
                "OMSId": self.oms_id,
                "Use2FA": False,
            },
            "Locked": False,
            "Requires2FA": False,
            "EnforceEnable2FA": False,
            "TwoFAType": None,
            "TwoFAToken": None,
            "errormsg": None,
        }
        return auth_resp

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_subscribes_to_orders_and_balances_events(self, ws_mock: AsyncMock):
        ws_mock.return_value = self.mocking_assistant.create_websocket_mock()

        subscribe_resp = {"m": 1, "i": 4, "n": "SubscribeAccountEvents", "o": json.dumps({"Subscribed": True})}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_mock.return_value, message=json.dumps(subscribe_resp)
        )

        output_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_mock.return_value)

        expected_auth_message = {
            CONSTANTS.MSG_TYPE_FIELD: CONSTANTS.REQ_MSG_TYPE,
            CONSTANTS.MSG_ENDPOINT_FIELD: CONSTANTS.WS_AUTH_ENDPOINT,
            CONSTANTS.MSG_SEQUENCE_FIELD: 2,
            CONSTANTS.MSG_DATA_FIELD: json.dumps(
                {
                    CONSTANTS.API_KEY_FIELD: self.api_key,
                    CONSTANTS.SIGNATURE_FIELD: self.signature,
                    CONSTANTS.USER_ID_FIELD: str(self.user_id),
                    CONSTANTS.NONCE_FIELD: self.nonce,
                }
            ),
        }
        expected_sub_message = {
            CONSTANTS.MSG_TYPE_FIELD: CONSTANTS.REQ_MSG_TYPE,
            CONSTANTS.MSG_ENDPOINT_FIELD: CONSTANTS.WS_ACC_EVENTS_ENDPOINT,
            CONSTANTS.MSG_SEQUENCE_FIELD: 4,
            CONSTANTS.MSG_DATA_FIELD: json.dumps(
                {
                    CONSTANTS.ACCOUNT_ID_FIELD: self.account_id,
                    CONSTANTS.OMS_ID_FIELD: self.oms_id,
                    CONSTANTS.API_KEY_FIELD: self.api_key,
                    CONSTANTS.SIGNATURE_FIELD: self.signature,
                    CONSTANTS.USER_ID_FIELD: str(self.user_id),
                    CONSTANTS.NONCE_FIELD: self.nonce,
                }
            ),
        }
        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_mock.return_value
        )

        self.assertEqual(2, len(sent_messages))
        self.assertEqual(expected_auth_message, sent_messages[0])
        self.assertEqual(expected_sub_message, sent_messages[1])

        self.assertTrue(
            self._is_logged(
                "INFO",
                "Subscribed to private account and orders channels..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_ignores_non_events(self, ws_mock):
        ws_mock.return_value = self.mocking_assistant.create_websocket_mock()

        subscribe_resp = {"m": 1, "i": 4, "n": "SubscribeAccountEvents", "o": json.dumps({"Subscribed": True})}
        update_data = {
            "AccountId": 23,
            "Amount": 5.5,
            "Hold": 3,
            "NotionalHoldAmount": 3,
            "NotionalProductId": 0,
            "NotionalProductSymbol": "ETH",
            "NotionalRate": 1,
            "NotionalValue": 5.5,
            "OMSId": 1,
            "PendingDeposits": 0,
            "PendingWithdraws": 0,
            "ProductId": 14,
            "ProductSymbol": "ETH",
            "TotalDayDepositNotional": 0,
            "TotalDayDeposits": 0,
            "TotalDayTransferNotional": 0,
            "TotalDayWithdrawNotional": 0,
            "TotalDayWithdraws": 0,
            "TotalMonthDepositNotional": 0,
            "TotalMonthDeposits": 0,
            "TotalMonthWithdrawNotional": 0,
            "TotalMonthWithdraws": 0,
            "TotalYearDepositNotional": 0,
            "TotalYearDeposits": 0,
            "TotalYearWithdrawNotional": 0,
            "TotalYearWithdraws": 0,
        }
        update_resp = {
            "m": 3,
            "i": 4,
            "n": "SubscribeAccountEvents",
            "o": json.dumps(update_data),
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_mock.return_value, message=json.dumps(subscribe_resp)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_mock.return_value, message=json.dumps(update_resp)
        )

        output_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_mock.return_value)

        self.assertFalse(output_queue.empty())

        expected_update_resp = {
            "m": 3,
            "i": 4,
            "n": "SubscribeAccountEvents",
            "o": update_data,
        }
        update_resp_received = output_queue.get_nowait()

        self.assertTrue(output_queue.empty())
        self.assertEqual(expected_update_resp, update_resp_received)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_sends_ping_message_before_ping_interval_finishes(self, ws_mock):
        ws_mock.return_value = self.mocking_assistant.create_websocket_mock()

        subscribe_resp = {"m": 1, "i": 4, "n": "SubscribeAccountEvents", "o": json.dumps({"Subscribed": True})}
        ws_mock.return_value.receive.side_effect = [
            WSMessage(type=WSMsgType.TEXT, data=json.dumps(subscribe_resp), extra=None),
            asyncio.TimeoutError("Test timeout"),
            asyncio.CancelledError,
        ]

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(websocket_mock=ws_mock.return_value)

        expected_ping_message = {"n": "Ping", "o": "{}", "m": 0, "i": 6}
        self.assertEqual(expected_ping_message, sent_messages[-1])
