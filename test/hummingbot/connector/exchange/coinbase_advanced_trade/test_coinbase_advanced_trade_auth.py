import hashlib
import hmac
from copy import copy
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses

from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_auth import CoinbaseAdvancedTradeAuth
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils import (
    get_current_server_time_s,
)
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class CoinbaseAdvancedTradeAuthTests(IsolatedAsyncioWrapperTestCase):

    def setUp(self) -> None:
        self.api_key = "testApiKey"
        self.secret_key = "testSecret"
        self.time_synchronizer_mock = AsyncMock(spec=TimeSynchronizer)
        self.auth = CoinbaseAdvancedTradeAuth(self.api_key, self.secret_key, self.time_synchronizer_mock)

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
            mocked.get("https://api.coinbase.com/api/v3/brokerage/time", payload=mock_response, status=200)

            current_server_time_s = await get_current_server_time_s()

            self.assertEqual(mock_response["epochSeconds"], current_server_time_s)

    # These are live test to verify the expectations of the server response unit. They will fail if there is a network issue
    #    async def test_get_current_server_time_s_fuzzy(self):
    #        # Get the local time in seconds since the Unix epoch
    #        local_time_s = time.time()
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

    #    async def test_get_current_server_time_ms_fuzzy(self, mock_aioresponse):
    #        # Get the local time in seconds since the Unix epoch
    #        local_time_ms = time.time() * 1000
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

    @aioresponses()
    async def test_rest_authenticate_on_public_time(self, mock_aioresponse):
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
            configured_request = await auth.rest_authenticate(request)

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

    @aioresponses()
    async def test_ws_authenticate(self, mock_aioresponse):
        ws_request = WSJSONRequest(payload={"channel": "level2", "product_ids": ["ETH-USD", "ETH-EUR"]})
        self.time_synchronizer_mock.update_server_time_offset_with_time_provider = AsyncMock(return_value=None)
        self.time_synchronizer_mock.time.side_effect = MagicMock(return_value=1234567890)

        # Mocking get_current_server_time_ms as an MagicMock on purpose since it is called
        # to get an Awaitable, but not awaited, which would generate a sys error and not look nice
        with patch('hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils'
                   '.get_current_server_time_ms',
                   new_callable=MagicMock) as mock_get_current_server_time_ms:
            mock_get_current_server_time_ms.return_value = 12345678900

            authenticated_request = await self.auth.ws_authenticate(ws_request)

        self.assertIsInstance(authenticated_request, WSJSONRequest)
        self.assertTrue("signature" in authenticated_request.payload)
        self.assertTrue("timestamp" in authenticated_request.payload)
        self.assertTrue("api_key" in authenticated_request.payload)
