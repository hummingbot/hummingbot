import hashlib
import hmac
import logging
from copy import copy
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
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
        self.secret_key = "testSecret"
        self.time_synchronizer_mock = AsyncMock(spec=TimeSynchronizer)
        self.auth = CoinbaseAdvancedTradeAuth(self.api_key, self.secret_key, self.time_synchronizer_mock)
        self.request = WSJSONRequest(payload={"type": "subscribe", "product_ids": ["ETH-USD", "ETH-EUR"], "channel": "level2"})

    async def asyncTearDown(self):
        logging.info("Close")
        if aiohttp.ClientSession()._connector is not None:
            logging.info("Close")
            await aiohttp.ClientSession().close()
        await super().asyncTearDown()

    def tearDown(self):
        super().tearDown()

    def test_init(self):
        self.assertEqual(self.auth.api_key, self.api_key)
        self.assertEqual(self.auth.secret_key, self.secret_key)
        self.assertEqual(self.auth.time_provider, self.time_synchronizer_mock)

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

    # These are live test to verify the expectations of the server response unit. They will fail if there is a network issue
    #    async def test_get_current_server_time_s_fuzzy(self):
    #        from time import time
    #        # Get the local time in seconds since the Unix epoch
    #        local_time_s = time()
    #
    #        # Get the server time in seconds since the Unix epoch
    #        server_time_s = await get_current_server_time_s()
    #
    #        # Calculate the time difference between the local and server times
    #        time_difference = abs(server_time_s - local_time_s)
    #
    #        # Allow for a tolerance of up to 5 seconds
    #        tolerance = 5
    #
    #        self.assertTrue(time_difference < tolerance, f"Time difference ({time_difference} seconds) is too large.")
    #
    #    @aioresponses()
    #    async def test_get_current_server_time_ms_fuzzy(self, mock_aioresponse):
    #        from time import time
    #        # Get the local time in seconds since the Unix epoch
    #        local_time_ms = time() * 1000
    #
    #        # Get the server time in seconds since the Unix epoch
    #        server_time_ms = await get_current_server_time_ms()
    #
    #        # Calculate the time difference between the local and server times
    #        time_difference_ms = abs(server_time_ms - local_time_ms)
    #
    #        # Allow for a tolerance of up to 5 seconds
    #        tolerance_ms = 5000
    #
    #        self.assertTrue(time_difference_ms < tolerance_ms,
    #                        f"Live Test: Time difference ({time_difference_ms} seconds) is too large.\n"
    #                        f"It is likely that there is a unit mismatch between the local and server times.\n"
    #                        f"Verify the API documentation and the assumptions of the implementation.")

    async def test_rest_legacy_authenticate_on_public_time(self):
        self.time_synchronizer_mock.time.side_effect = MagicMock(return_value=1234567890)

        params = {
            "extra_param": "Test",
        }
        full_params = copy(params)

        auth = CoinbaseAdvancedTradeAuth(api_key=self.api_key, secret_key=self.secret_key,
                                         time_provider=self.time_synchronizer_mock)
        url = "https://api.coinbase.com/v2/time"
        request = RESTRequest(method=RESTMethod.GET, url=url, params=params, is_auth_required=True)
        # Mocking get_current_server_time_ms as an MagicMock on purpose since it is called
        # to get an Awaitable, but not awaited, which would generate a sys error and not look nice
        with patch('hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils'
                   '.get_current_server_time_ms',
                   new_callable=MagicMock) as mocked_time:
            mocked_time.return_value = 1234567890.0
            configured_request = await auth.rest_legacy_authenticate(request)

        full_params.update({"timestamp": "1234567890"})
        # full url is parsed-down to endpoint only
        encoded_params = "1234567890" + str(RESTMethod.GET) + "/v2/time" + str(request.data or '')
        expected_signature = hmac.new(
            self.secret_key.encode("utf-8"),
            encoded_params.encode("utf-8"),
            hashlib.sha256).hexdigest()

        self.assertEqual("application/json", configured_request.headers["accept"])
        self.assertEqual(self.api_key, configured_request.headers["CB-ACCESS-KEY"])
        self.assertEqual("1234567890", configured_request.headers["CB-ACCESS-TIMESTAMP"])
        self.assertEqual(expected_signature, configured_request.headers["CB-ACCESS-SIGN"])

    async def test_ws_legacy_authenticate(self):
        ws_request = WSJSONRequest(payload={"channel": "level2", "product_ids": ["ETH-USD", "ETH-EUR"]})
        self.time_synchronizer_mock.update_server_time_offset_with_time_provider = AsyncMock(return_value=None)
        self.time_synchronizer_mock.time.side_effect = MagicMock(return_value=1234567890)

        # Mocking get_current_server_time_ms as an MagicMock on purpose since it is called
        # to get an Awaitable, but not awaited, which would generate a sys error and not look nice
        with patch('hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils'
                   '.get_current_server_time_ms',
                   new_callable=MagicMock) as mock_get_current_server_time_ms:
            mock_get_current_server_time_ms.return_value = 12345678900

            authenticated_request = await self.auth.ws_legacy_authenticate(ws_request)

        self.assertIsInstance(authenticated_request, WSJSONRequest)
        self.assertTrue("signature" in authenticated_request.payload)
        self.assertTrue("timestamp" in authenticated_request.payload)
        self.assertTrue("api_key" in authenticated_request.payload)

    @patch('jwt.encode')
    async def test_ws_jwt_authenticate(self, mock_encode):
        self.auth.secret_key = pem_private_key_str
        self.time_synchronizer_mock.time.side_effect = MagicMock(return_value=12345678900)
        result = await self.auth.ws_jwt_authenticate(self.request)
        self.assertIn('jwt', result.payload)
        mock_encode.assert_called_once()

    @patch('jwt.encode')
    def test_build_jwt(self, mock_encode):
        self.auth.secret_key = pem_private_key_str
        mock_encode.return_value = 'test_jwt_token'
        result = self.auth._build_jwt(service='test_service', uri='test_uri')
        self.assertEqual('test_jwt_token', result, )
        mock_encode.assert_called_once()

    def test_build_jwt_invalid_secret_key(self):
        self.auth.secret_key = 'invalid_secret_key'
        with self.assertRaises(ValueError):
            self.auth._build_jwt(service='test_service', uri='test_uri')

    @patch('jwt.encode')
    def test_build_jwt_fields(self, mock_encode):
        self.auth.secret_key = pem_private_key_str
        mock_encode.return_value = 'test_jwt_token'
        self.auth._build_jwt(service='test_service', uri='test_uri')
        args, kwargs = mock_encode.call_args
        jwt_data = args[0]
        self.assertEqual(self.auth.api_key, jwt_data['sub'])
        self.assertEqual('coinbase-cloud', jwt_data['iss'], )
        self.assertEqual(['test_service'], jwt_data['aud'], )
        self.assertEqual('test_uri', jwt_data['uri'], )

    @patch('jwt.encode')
    def test_build_jwt_algorithm_and_headers(self, mock_encode):
        self.auth.secret_key = pem_private_key_str
        mock_encode.return_value = 'test_jwt_token'
        self.auth._build_jwt(service='test_service', uri='test_uri')
        args, kwargs = mock_encode.call_args
        self.assertEqual('ES256', kwargs['algorithm'], )
        self.assertEqual(self.auth.api_key, kwargs['headers']['kid'])
        self.assertTrue(isinstance(kwargs['headers']['nonce'], str))

    def test_secret_key_pem_already_in_pem_format(self):
        self.auth.secret_key = ("-----BEGIN EC PRIVATE "
                                "KEY-----\n_private_key__private_key_private_key_private_key_private_key_pr"
                                "\nivate_key_\n-----END EC PRIVATE"
                                " KEY-----\n")
        # The key is fake, it will fail the serialization attempt
        with self.assertRaises(ValueError):
            self.assertEqual(self.auth._secret_key_pem(), self.auth.secret_key.strip())

    def test_secret_key_pem_in_base64_format(self):
        self.auth.secret_key = "_private_key__private_key_private_key_private_key_private_key_private_key_"
        expected_output = ("-----BEGIN EC PRIVATE "
                           "KEY-----\n_private_key__private_key_private_key_private_key_private_key_pr\nivate_key_\n"
                           "-----END EC PRIVATE"
                           " KEY-----")
        # The key is fake, it will fail the serialization attempt
        with self.assertRaises(ValueError):
            self.assertEqual(self.auth._secret_key_pem(), expected_output)

    def test_secret_key_pem_in_single_line_pem_format(self):
        self.auth.secret_key = ("-----BEGIN EC PRIVATE "
                                "KEY-----_private_key__private_key_private_key_private_key_private_key_private_key_"
                                "-----END EC PRIVATE"
                                " KEY-----")
        expected_output = ("-----BEGIN EC PRIVATE "
                           "KEY-----\n_private_key__private_key_private_key_private_key_private_key_pr\nivate_key_\n"
                           "-----END EC PRIVATE"
                           " KEY-----")
        with self.assertRaises(ValueError):
            self.assertEqual(self.auth._secret_key_pem(), expected_output)

    def test_valid_secret_key_pem_in_base64_format(self):
        self.auth.secret_key = pem_private_key_str
        self.auth._secret_key_pem()
