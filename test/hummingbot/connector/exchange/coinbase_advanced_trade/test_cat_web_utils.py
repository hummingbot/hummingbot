import asyncio
import unittest
from unittest.mock import ANY, AsyncMock, Mock, patch

import hummingbot.connector.exchange.coinbase_advanced_trade.cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_web_utils import (
    build_api_factory,
    build_api_factory_without_time_synchronizer_pre_processor,
    create_throttler,
    get_current_server_time_ms,
    get_current_server_time_s,
    get_timestamp_from_exchange_time,
    private_rest_url,
    public_rest_url,
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class CoinbaseAdvancedTradeUtilTestCases(unittest.TestCase):

    def test_public_rest_url(self):
        # Test default domain
        self.assertEqual(
            public_rest_url('/test'),
            CONSTANTS.REST_URL.format(domain=CONSTANTS.DEFAULT_DOMAIN) + '/test'
        )

        # Test custom domain
        self.assertEqual(
            public_rest_url('/test', domain='us'),
            CONSTANTS.REST_URL.format(domain='us') + '/test'
        )

        # Test signin url endpoints
        for endpoint in CONSTANTS.SIGNIN_ENDPOINTS:
            self.assertEqual(
                public_rest_url(endpoint),
                CONSTANTS.SIGNIN_URL.format(domain=CONSTANTS.DEFAULT_DOMAIN) + endpoint
            )

    def test_private_rest_url(self):
        # Similar to the public_rest_url, just replace the function call
        self.assertEqual(
            private_rest_url('/test'),
            CONSTANTS.REST_URL.format(domain=CONSTANTS.DEFAULT_DOMAIN) + '/test'
        )

        # Test custom domain
        self.assertEqual(
            private_rest_url('/test', domain='us'),
            CONSTANTS.REST_URL.format(domain='us') + '/test'
        )

        # Test signin url endpoints
        for endpoint in CONSTANTS.SIGNIN_ENDPOINTS:
            self.assertEqual(
                private_rest_url(endpoint),
                CONSTANTS.SIGNIN_URL.format(domain=CONSTANTS.DEFAULT_DOMAIN) + endpoint
            )

    def test_create_throttler(self):
        throttler = create_throttler()
        self.assertIsInstance(throttler, AsyncThrottler)

    @patch.object(WebAssistantsFactory, "__init__", return_value=None)
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.cat_web_utils"
           ".create_throttler", return_value=Mock())
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.cat_web_utils"
           ".get_current_server_time_s")
    def test_build_api_factory(self, mock_get_current_server_time_s, mock_create_throttler, mock_init):
        mock_get_current_server_time_s.return_value = 123456
        create_throttler()
        build_api_factory()
        mock_create_throttler.assert_called_once()
        mock_init.assert_called_once_with(
            throttler=mock_create_throttler.return_value,
            auth=None,
            rest_pre_processors=[ANY]

        )

    @patch.object(WebAssistantsFactory, "__init__", return_value=None)
    def test_build_api_factory_without_time_synchronizer_pre_processor(self, mock_factory):
        throttler = Mock()
        build_api_factory_without_time_synchronizer_pre_processor(throttler)
        mock_factory.assert_called_once_with(throttler=throttler)

    @patch('hummingbot.connector.exchange.coinbase_advanced_trade.cat_web_utils'
           '.get_current_server_time_s')
    def test_get_current_server_time_ms(self, mock_get_time_s):
        async def async_test():
            mock_get_time_s.return_value = 1
            result = await get_current_server_time_ms()
            self.assertEqual(result, 1000)

        asyncio.run(async_test())

    def test_get_timestamp_from_exchange_time(self):
        # Test with seconds
        expected_seconds = 1683808496.789012
        self.assertEqual(get_timestamp_from_exchange_time('2023-05-11T12:34:56.789012+00:00', 's'), expected_seconds)

        # Test with milliseconds
        expected_milliseconds = expected_seconds * 1000
        self.assertEqual(get_timestamp_from_exchange_time('2023-05-11T12:34:56.789012+00:00', 'ms'),
                         expected_milliseconds)

        # Test with long string
        self.assertEqual(get_timestamp_from_exchange_time('2023-05-11T12:34:56.7890123456+00:00', 'ms'),
                         expected_milliseconds)

        # Test with different units
        self.assertEqual(get_timestamp_from_exchange_time('2023-05-11T12:34:56.789012+00:00', 'seconds'),
                         expected_seconds)
        self.assertEqual(get_timestamp_from_exchange_time('2023-05-11T12:34:56.789012+00:00', 'second'),
                         expected_seconds)
        self.assertEqual(get_timestamp_from_exchange_time('2023-05-11T12:34:56.789012+00:00', 'milliseconds'),
                         expected_milliseconds)
        self.assertEqual(get_timestamp_from_exchange_time('2023-05-11T12:34:56.789012+00:00', 'millisecond'),
                         expected_milliseconds)

    @patch(
        'hummingbot.connector.exchange.coinbase_advanced_trade.cat_web_utils'
        '.build_api_factory_without_time_synchronizer_pre_processor',
        new_callable=Mock)
    @patch('hummingbot.connector.exchange.coinbase_advanced_trade.cat_web_utils.public_rest_url')
    def test_get_current_server_time_s(self, mock_public_rest_url, mock_api_factory):
        async def async_test():
            # Prepare Mocks
            mock_public_rest_url.return_value = 'mock_url'
            mock_rest_assistant = AsyncMock()
            mock_rest_assistant.execute_request.return_value = {"data": {"iso": "2007-04-05T14:30Z", "epoch": 1175783400}}

            async def get_rest_assistant():
                return mock_rest_assistant

            mock_api_factory.return_value.get_rest_assistant = get_rest_assistant

            # Run Test
            server_time = await get_current_server_time_s()

            # Assertions
            mock_public_rest_url.assert_called_with(path_url=CONSTANTS.SERVER_TIME_EP, domain=CONSTANTS.DEFAULT_DOMAIN)
            mock_rest_assistant.execute_request.assert_called_with(
                url='mock_url',
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.SERVER_TIME_EP,
            )
            self.assertEqual(server_time, 1175783400)

        asyncio.run(async_test())


if __name__ == "__main__":
    unittest.main()
