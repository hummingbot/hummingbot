import asyncio
import json
import re
import time
from typing import Awaitable
from unittest import TestCase
from unittest.mock import patch

from aioresponses import aioresponses

from hummingbot.connector.exchange.ndax import ndax_web_utils as web_utils
from hummingbot.connector.exchange.ndax.ndax_auth import NdaxAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class NdaxAuthTests(TestCase):

    def setUp(self) -> None:
        self._uid: str = '001'
        self._account_id = 1
        self._api_key: str = 'test_api_key'
        self._secret_key: str = 'test_secret_key'
        self._account_name: str = "hbot"
        self._token: str = "123"
        self._initialized = True

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_authentication_headers(self):
        auth = NdaxAuth(uid=self._uid, api_key=self._api_key, secret_key=self._secret_key, account_name=self._account_name)
        auth.token = self._token
        auth.uid = self._uid
        auth._token_expiration = time.time() + 7200
        auth._initialized = True
        request = RESTRequest(method=RESTMethod.GET, params={}, is_auth_required=True)
        headers = self.async_run_with_timeout(auth.rest_authenticate(request))

        self.assertEqual(2, len(headers.headers))
        self.assertEqual('application/json', headers.headers.get("Content-Type"))
        self.assertEqual(self._token, headers.headers.get('APToken'))

    @aioresponses()
    def test_rest_authentication_to_endpoint_authenticated(self, mock_api):
        url = web_utils.public_rest_url(path_url="Authenticate", domain="ndax_main")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = {'Authenticated': True, 'SessionToken': self._token, 'User': {'UserId': 169072, 'UserName': 'hbot', 'Email': 'hbot@mailinator.com', 'EmailVerified': True, 'AccountId': 169418, 'OMSId': 1, 'Use2FA': True}, 'Locked': False, 'Requires2FA': False, 'EnforceEnable2FA': False, 'TwoFAType': None, 'TwoFAToken': None, 'errormsg': None}

        mock_api.post(regex_url, body=json.dumps(resp))
        auth = NdaxAuth(uid=self._uid, api_key=self._api_key, secret_key=self._secret_key, account_name=self._account_name)
        auth.token = self._token
        auth.uid = self._uid
        auth._initialized = True
        request = RESTRequest(method=RESTMethod.GET, params={}, is_auth_required=True)
        headers = self.async_run_with_timeout(auth.rest_authenticate(request))

        self.assertEqual(2, len(headers.headers))
        self.assertEqual('application/json', headers.headers.get("Content-Type"))
        self.assertEqual(self._token, headers.headers.get('APToken'))

    @aioresponses()
    async def test_rest_authentication_to_endpoint_not_authenticated(self, mock_api):
        url = web_utils.public_rest_url(path_url="Authenticate", domain="ndax_main")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = {}

        mock_api.post(regex_url, body=json.dumps(resp))
        auth = NdaxAuth(uid=self._uid, api_key=self._api_key, secret_key=self._secret_key, account_name=self._account_name)
        auth.token = self._token
        auth.uid = self._uid
        auth._initialized = True
        request = RESTRequest(method=RESTMethod.GET, params={}, is_auth_required=True)
        with self.assertRaises(Exception):
            await auth.rest_authenticate(request)

    def test_ws_auth_payload(self):
        auth = NdaxAuth(uid=self._uid, api_key=self._api_key, secret_key=self._secret_key, account_name=self._account_name)
        auth.token = self._token
        auth.uid = self._uid
        auth._token_expiration = time.time() + 7200
        auth._initialized = True
        request = RESTRequest(method=RESTMethod.GET, params={}, is_auth_required=True)
        auth_info = self.async_run_with_timeout(auth.ws_authenticate(request=request))

        self.assertEqual(request, auth_info)

    def test_header_for_authentication(self):
        auth = NdaxAuth(uid=self._uid, api_key=self._api_key, secret_key=self._secret_key, account_name=self._account_name)
        nonce = '1234567890'

        with patch('hummingbot.connector.exchange.ndax.ndax_auth.get_tracking_nonce_low_res') as generate_nonce_mock:
            generate_nonce_mock.return_value = nonce
            auth_info = auth.header_for_authentication()

        self.assertEqual(4, len(auth_info))
        self.assertEqual(self._uid, auth_info.get('UserId'))
        self.assertEqual(nonce, auth_info.get('Nonce'))
