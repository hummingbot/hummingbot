import asyncio
import hashlib
import hmac
import time
from copy import copy
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_auth import CoinbaseAdvancedTradeAuth
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_web_utils import (
    get_current_server_time_ms,
    get_current_server_time_s,
)
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class CoinbaseAdvancedTradeAuthTests(TestCase):

    def setUp(self) -> None:
        self.api_key = "testApiKey"
        self.secret_key = "testSecret"
        self.time_synchronizer_mock = AsyncMock(spec=TimeSynchronizer)
        self.auth = CoinbaseAdvancedTradeAuth(self.api_key, self.secret_key, self.time_synchronizer_mock)

    def test_init(self):
        self.assertEqual(self.auth.api_key, self.api_key)
        self.assertEqual(self.auth.secret_key, self.secret_key)
        self.assertEqual(self.auth.time_provider, self.time_synchronizer_mock)

    def test_get_current_server_time_s(self):
        async def _async_test():
            async with aioresponses() as mocked:
                mock_response = {
                    "iso": "2023-05-09T18:47:30.000Z",
                    "epoch": 1664000045.135
                }
                mocked.get("https://api.coinbase.com/v2/time", payload=mock_response, status=200)

                current_server_time_s = await get_current_server_time_s()

                self.assertEqual(current_server_time_s, mock_response["epoch"])

            asyncio.run(_async_test())

    def test_get_current_server_time_s_fuzzy(self):
        async def async_test():
            # Get the local time in seconds since the Unix epoch
            local_time_s = time.time()

            # Get the server time in seconds since the Unix epoch
            server_time_s = await get_current_server_time_s()

            # Calculate the time difference between the local and server times
            time_difference = abs(server_time_s - local_time_s)

            # Allow for a tolerance of up to 5 seconds
            tolerance = 5

            self.assertTrue(time_difference < tolerance, f"Time difference ({time_difference} seconds) is too large.")

        asyncio.run(async_test())

    def test_get_current_server_time_ms_fuzzy(self):
        async def async_test():
            # Get the local time in seconds since the Unix epoch
            local_time_ms = time.time() * 1000

            # Get the server time in seconds since the Unix epoch
            server_time_ms = await get_current_server_time_ms()

            # Calculate the time difference between the local and server times
            time_difference_ms = abs(server_time_ms - local_time_ms)

            # Allow for a tolerance of up to 5 seconds
            tolerance_ms = 5000

            self.assertTrue(time_difference_ms < tolerance_ms,
                            f"Time difference ({time_difference_ms} seconds) is too large.")

        asyncio.run(async_test())

    def test_rest_authenticate_on_public_time(self):
        async def async_test():
            self.time_synchronizer_mock.time.side_effect = MagicMock(return_value=1234567890)

            params = {
                "extra_param": "Test",
            }
            full_params = copy(params)

            auth = CoinbaseAdvancedTradeAuth(api_key=self.api_key, secret_key=self.secret_key,
                                             time_provider=self.time_synchronizer_mock)
            url = "/time"
            request = RESTRequest(method=RESTMethod.GET, url=url, params=params, is_auth_required=True)
            # Mocking get_current_server_time_ms as an MagicMock on purpose since it is called
            # to get an Awaitable, but not awaited, which would generate a sys error and not look nice
            with patch('hummingbot.connector.exchange.coinbase_advanced_trade.cat_auth'
                       '.get_current_server_time_ms',
                       new_callable=MagicMock):
                configured_request = await auth.rest_authenticate(request)

            full_params.update({"timestamp": "1234567890"})
            encoded_params = "1234567890" + str(RESTMethod.GET) + url + str(request.data or '')
            expected_signature = hmac.new(
                self.secret_key.encode("utf-8"),
                encoded_params.encode("utf-8"),
                hashlib.sha256).hexdigest()

            self.assertEqual("application/json", configured_request.headers["accept"])
            self.assertEqual(self.api_key, configured_request.headers["CB-ACCESS-KEY"])
            self.assertEqual(1234567890, configured_request.headers["CB-ACCESS-TIMESTAMP"])
            self.assertEqual(expected_signature, configured_request.headers["CB-ACCESS-SIGN"])

        asyncio.run(async_test())

    def test_ws_authenticate(self):
        async def async_test():
            ws_request = WSJSONRequest(payload={"channel": "level2", "product_ids": ["ETH-USD", "ETH-EUR"]})
            self.time_synchronizer_mock.update_server_time_offset_with_time_provider = AsyncMock(return_value=None)
            self.time_synchronizer_mock.time.side_effect = MagicMock(return_value=1234567890)

            # Mocking get_current_server_time_ms as an MagicMock on purpose since it is called
            # to get an Awaitable, but not awaited, which would generate a sys error and not look nice
            with patch('hummingbot.connector.exchange.coinbase_advanced_trade.cat_auth'
                       '.get_current_server_time_ms',
                       new_callable=MagicMock) as mock_get_current_server_time_ms:
                mock_get_current_server_time_ms.return_value = 12345678900

                authenticated_request = await self.auth.ws_authenticate(ws_request)

                self.assertIsInstance(authenticated_request, WSJSONRequest)
                self.assertTrue("signature" in authenticated_request.payload)
                self.assertTrue("timestamp" in authenticated_request.payload)
                self.assertTrue("api_key" in authenticated_request.payload)

        asyncio.run(async_test())

    def test__get_synced_timestamp_s_time_sync_methods_called(self):
        async def async_test():
            # Mock time to return a large enough value so that time sync update is triggered
            self.time_synchronizer_mock.time.return_value = CoinbaseAdvancedTradeAuth.TIME_SYNC_UPDATE_S + 1

            await self.auth._get_synced_timestamp_s()

            self.time_synchronizer_mock.time.assert_called()
            self.time_synchronizer_mock.update_server_time_offset_with_time_provider.assert_called_once()

        asyncio.run(async_test())

    def test__get_synced_timestamp_s_get_current_server_time_called(self):
        async def async_test():
            # Mock update_server_time_offset_with_time_provider to return None
            self.time_synchronizer_mock.update_server_time_offset_with_time_provider.return_value = None

            await self.auth._get_synced_timestamp_s()

            self.time_synchronizer_mock.update_server_time_offset_with_time_provider.assert_called_once()

        asyncio.run(async_test())

    def test__get_synced_timestamp_s_time_sync_return_value(self):
        async def async_test():
            server_time_ms = await get_current_server_time_ms()
            server_time_s = server_time_ms / 1000

            # Mock time to return server time
            self.time_synchronizer_mock.time.return_value = server_time_s

            returned_time = await self.auth._get_synced_timestamp_s()

            self.time_synchronizer_mock.time.assert_called()
            self.assertAlmostEqual(returned_time, int(server_time_s), delta=1)

        asyncio.run(async_test())

    def test__get_synced_timestamp_s(self):
        async def async_test():
            self.auth._time_sync_last_updated_s = -1
            self.time_synchronizer_mock.time.return_value = 1234567890

            # Mocking get_current_server_time_ms as an MagicMock on purpose since it is called
            # to get an Awaitable, but not awaited, which would generate a sys error and not look nice
            with patch('hummingbot.connector.exchange.coinbase_advanced_trade.cat_auth'
                       '.get_current_server_time_ms',
                       new_callable=MagicMock) as mock_get_current_server_time_ms:
                mock_get_current_server_time_ms.return_value = asyncio.Future()
                mock_get_current_server_time_ms.return_value.set_result(1234567890 * 1000)

                synced_timestamp = await self.auth._get_synced_timestamp_s()

                self.time_synchronizer_mock.update_server_time_offset_with_time_provider.assert_called_once()
                called_with_coroutine = \
                    self.time_synchronizer_mock.update_server_time_offset_with_time_provider.call_args[0][0]
                self.assertTrue(isinstance(called_with_coroutine, asyncio.Future))
                self.assertEqual(synced_timestamp, 1234567890)

        asyncio.run(async_test())
