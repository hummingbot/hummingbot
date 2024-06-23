import hashlib
import hmac
import logging
from copy import copy
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import jwt
from aioresponses import aioresponses
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

import hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_auth import CoinbaseAdvancedTradeAuth
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils import (
    get_current_server_time_s,
    private_rest_url,
)
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest

# This is the algorithm used by Coinbase Advanced Trade
private_key = ec.generate_private_key(
    ec.SECP256R1(),  # This is equivalent to ES256
    backend=default_backend()
)

# Serialize the private key to PEM format
pem_private_key = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

# Convert the PEM private key to string
pem_private_key_str = pem_private_key.decode('utf-8')


class CoinbaseAdvancedTradeAuthTests(IsolatedAsyncioWrapperTestCase):

    def setUp(self) -> None:
        self.api_key = "testApiKey"
        self.legacy_secret_key = "testSecret"
        self.cdp_secret_key = pem_private_key_str
        self.cdp_token = jwt.encode({'some': 'payload'}, self.cdp_secret_key, algorithm='ES256', headers={'kid': self.api_key})

        self.time_synchronizer_mock = AsyncMock(spec=TimeSynchronizer)
        self.legacy_auth = CoinbaseAdvancedTradeAuth(self.api_key, self.legacy_secret_key, self.time_synchronizer_mock)
        self.cdp_auth = CoinbaseAdvancedTradeAuth(self.api_key, self.cdp_secret_key, self.time_synchronizer_mock)
        self.ws_request = WSJSONRequest(
            payload={"type": "subscribe", "product_ids": ["ETH-USD", "ETH-EUR"], "channel": "level2"})
        self.rest_request = RESTRequest(method=RESTMethod.GET, url="https://api.coinbase.com/v2/time",
                                        is_auth_required=True)

    async def asyncTearDown(self):
        logging.info("Close")
        if aiohttp.ClientSession()._connector is not None:
            logging.info("Close")
            await aiohttp.ClientSession().close()
        await super().asyncTearDown()

    def tearDown(self):
        super().tearDown()

    def test_valid_token(self):
        result = CoinbaseAdvancedTradeAuth.is_token_valid(self.cdp_token, self.cdp_secret_key)
        self.assertTrue(result)

    def test_invalid_token(self):
        invalid_token = f'{self.cdp_token}make_it_invalid'
        result = CoinbaseAdvancedTradeAuth.is_token_valid(invalid_token, self.cdp_secret_key)
        self.assertFalse(result)

    def test_init(self):
        self.assertEqual(self.legacy_auth.api_key, self.api_key)
        self.assertEqual(self.legacy_auth.secret_key, self.legacy_secret_key)
        self.assertEqual(self.legacy_auth.time_provider, self.time_synchronizer_mock)
        self.assertEqual(self.cdp_auth.api_key, self.api_key)
        self.assertEqual(self.cdp_auth.secret_key, self.cdp_secret_key)
        self.assertEqual(self.cdp_auth.time_provider, self.time_synchronizer_mock)

    async def test_get_current_server_time_s(self):
        with aioresponses() as mocked:
            # Note that Coinbase provide most of its time in ISO8601 format, the time endpoint provides both
            # ISO8601 and epoch time, however, for sake of consistency, we use the iso format in the
            # get_current_server_time_s method - Make sure the response is self-consistent
            mock_response = {
                "iso": "2023-05-09T18:47:30.000Z",
                "epochSeconds": 1683658050,
                "epochMillis": 1683658050123
            }
            mocked.get(private_rest_url(CONSTANTS.SERVER_TIME_EP), payload=mock_response, status=200)

            # This is to suppress the annoying warnings from the
            # ill-conceived aiohttp.ClientSession from the ConnectionsFactory
            # that does not cleanly close a session or use a correct context manager
            # This was solved a year ago, according to F.C.
            async with aiohttp.ClientSession() as session:
                with patch('aiohttp.ClientSession') as mock_session:
                    mock_session.return_value = session
                    current_server_time_s = await get_current_server_time_s()

            self.assertEqual(mock_response["epochSeconds"], current_server_time_s)

    def test_rest_legacy_authenticate_on_public_time(self):
        self.time_synchronizer_mock.time.side_effect = MagicMock(return_value=1234567890)

        params = {
            "extra_param": "Test",
        }
        full_params = copy(params)

        auth = CoinbaseAdvancedTradeAuth(api_key=self.api_key, secret_key=self.legacy_secret_key,
                                         time_provider=self.time_synchronizer_mock)
        url = "https://api.coinbase.com/v2/time"
        request = RESTRequest(method=RESTMethod.GET, url=url, params=params, is_auth_required=True)
        # Mocking get_current_server_time_ms as an MagicMock on purpose since it is called
        # to get an Awaitable, but not awaited, which would generate a sys error and not look nice
        with patch('hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils'
                   '.get_current_server_time_ms',
                   new_callable=MagicMock) as mocked_time:
            mocked_time.return_value = 1234567890.0
            configured_request = auth.rest_legacy_authenticate(request)

        full_params.update({"timestamp": "1234567890"})
        # full url is parsed-down to endpoint only
        encoded_params = "1234567890" + str(RESTMethod.GET) + "/v2/time" + str(request.data or '')
        expected_signature = hmac.new(
            self.legacy_secret_key.encode("utf-8"),
            encoded_params.encode("utf-8"),
            hashlib.sha256).hexdigest()

        self.assertEqual("application/json", configured_request.headers["accept"])
        self.assertEqual(self.api_key, configured_request.headers["CB-ACCESS-KEY"])
        self.assertEqual("1234567890", configured_request.headers["CB-ACCESS-TIMESTAMP"])
        self.assertEqual(expected_signature, configured_request.headers["CB-ACCESS-SIGN"])

    def test_ws_legacy_authenticate(self):
        ws_request = WSJSONRequest(payload={"channel": "level2", "product_ids": ["ETH-USD", "ETH-EUR"]})
        self.time_synchronizer_mock.update_server_time_offset_with_time_provider = AsyncMock(return_value=None)
        self.time_synchronizer_mock.time.side_effect = MagicMock(return_value=1234567890)

        # Mocking get_current_server_time_ms as an MagicMock on purpose since it is called
        # to get an Awaitable, but not awaited, which would generate a sys error and not look nice
        with patch('hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils'
                   '.get_current_server_time_ms',
                   new_callable=MagicMock) as mock_get_current_server_time_ms:
            mock_get_current_server_time_ms.return_value = 12345678900

            authenticated_request = self.legacy_auth.ws_legacy_authenticate(ws_request)

        self.assertIsInstance(authenticated_request, WSJSONRequest)
        self.assertTrue("signature" in authenticated_request.payload)
        self.assertTrue("timestamp" in authenticated_request.payload)
        self.assertTrue("api_key" in authenticated_request.payload)

    def test_rest_jwt_authenticate(self):
        self.time_synchronizer_mock.time.side_effect = MagicMock(return_value=1719164082)

        result = self.cdp_auth.rest_jwt_authenticate(self.rest_request)

        self.assertIn('Authorization', result.headers)
        self.assertIn('User-Agent', result.headers)
        self.assertIn('content-type', result.headers)
        token = result.headers["Authorization"].split(" ")[1]
        self.assertTrue(
            CoinbaseAdvancedTradeAuth.is_token_valid(token, self.cdp_auth.secret_key))

    def test_ws_jwt_authenticate(self):
        result = self.cdp_auth.ws_jwt_authenticate(self.ws_request)
        self.assertIn('jwt', result.payload)
        self.assertTrue(
            CoinbaseAdvancedTradeAuth.is_token_valid(result.payload['jwt'], self.cdp_auth.secret_key))
