from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase

from aioresponses.core import aioresponses

from hummingbot.connector.exchange.kalqix import kalqix_constants as CONSTANTS, kalqix_web_utils as web_utils
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class KalqixWebUtilsTests(IsolatedAsyncioWrapperTestCase):

    def test_rest_url_default_domain(self):
        self.assertEqual(
            "https://api.kalqix.com/v1/markets",
            web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain="com"),
        )

    def test_rest_url_testnet_domain(self):
        self.assertEqual(
            "https://testnet-api.kalqix.com/v1/markets",
            web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain="testnet"),
        )

    def test_public_and_private_rest_url_are_aliases(self):
        self.assertEqual(
            web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL, domain="com"),
            web_utils.public_rest_url(CONSTANTS.ORDERS_PATH_URL, domain="com"),
        )
        self.assertEqual(
            web_utils.rest_url(CONSTANTS.ORDERS_PATH_URL, domain="com"),
            web_utils.private_rest_url(CONSTANTS.ORDERS_PATH_URL, domain="com"),
        )

    def test_build_api_factory_wires_time_synchronizer_pre_processor(self):
        api_factory = web_utils.build_api_factory()
        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertTrue(
            any(isinstance(pre_processor, TimeSynchronizerRESTPreProcessor)
                for pre_processor in api_factory._rest_pre_processors)
        )

    def test_build_api_factory_without_time_synchronizer_pre_processor(self):
        throttler = web_utils.create_throttler()
        api_factory = web_utils.build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertEqual(0, len(api_factory._rest_pre_processors))

    @aioresponses()
    async def test_get_current_server_time_reads_server_time_field(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_PATH_URL, domain="com")
        mock_api.get(url, body='{"server_time": 1640000000000}')

        server_time = await web_utils.get_current_server_time(domain="com")

        self.assertEqual(1640000000000, server_time)
