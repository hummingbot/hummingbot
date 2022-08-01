import asyncio
import hashlib
import hmac
import unittest
from typing import Any, Awaitable
from unittest.mock import MagicMock, patch

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utilities.oms_connector.oms_connector_auth import OMSConnectorAuth
from hummingbot.connector.utilities.oms_connector.oms_connector_web_utils import build_api_factory


class OMSConnectorAuthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ev_loop = asyncio.get_event_loop()
        cls.api_key = "someApiKey"
        cls.secret = "someSecret"
        cls.user_id = 20
        cls.time_mock = 1655283229.419752
        cls.user_name = "someUserName"
        cls.account_id = 3
        cls.ws_url = "ws://someUrl"

    @patch("hummingbot.core.utils.tracking_nonce.NonceCreator._time")
    def setUp(self, time_mock: MagicMock) -> None:
        super().setUp()
        time_mock.return_value = self.time_mock
        self.auth = OMSConnectorAuth(self.api_key, self.secret, self.user_id)
        self.api_factory = build_api_factory(auth=self.auth)
        self.ws_assistant = self.async_run_with_timeout(self.api_factory.get_ws_assistant())
        self.mocking_assistant = NetworkMockingAssistant()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1) -> Any:
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_build_auth_payload(self):
        nonce = str(int(self.time_mock * 1e3))
        concat = f"{nonce}{self.user_id}{self.api_key}"
        signature = hmac.new(
            key=self.secret.encode("utf-8"),
            msg=concat.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        expected_headers = {
            "APIKey": self.api_key,
            "Signature": signature,
            "UserId": str(self.user_id),
            "Nonce": nonce,
        }

        auth_payload = self.auth.get_rest_auth_headers()

        self.assertEqual(expected_headers, auth_payload)

    def test_validate_auth(self):
        response_success = {
            "Authenticated": True,
            "SessionToken": "0e8bbcbc-6ada-482a-a9b4-5d9218ada3f9",
            "User": {
                "UserId": self.user_id,
                "UserName": self.user_name,
                "Email": "",
                "EmailVerified": True,
                "AccountId": self.account_id,
                "OMSId": 1,
                "Use2FA": False,
            },
            "Locked": False,
            "Requires2FA": False,
            "EnforceEnable2FA": False,
            "TwoFAType": None,
            "TwoFAToken": None,
            "errormsg": None,
        }

        self.assertTrue(self.auth.validate_rest_auth(response_success))

        self.assertNotEqual(self.user_name, self.auth.user_name)
        self.assertNotEqual(self.account_id, self.auth.account_id)
        self.assertFalse(self.auth.initialized)

        self.auth.update_with_rest_response(response_success)

        self.assertEqual(self.user_name, self.auth.user_name)
        self.assertEqual(self.account_id, self.auth.account_id)
        self.assertTrue(self.auth.initialized)

        response_failure = {
            "Authenticated": False,
            "EnforceEnable2FA": False,
            "Locked": False,
            "Requires2FA": False,
            "SessionToken": None,
            "TwoFAToken": None,
            "TwoFAType": None,
            "User": {
                "AccountId": 0,
                "Email": None,
                "EmailVerified": False,
                "OMSId": 0,
                "Use2FA": False,
                "UserId": 0,
                "UserName": None,
            },
            "errormsg": "User api key not found",
        }

        self.assertFalse(self.auth.validate_rest_auth(response_failure))
