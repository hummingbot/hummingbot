from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.grvt_perpetual import (
    grvt_perpetual_constants as CONSTANTS,
    grvt_perpetual_web_utils as web_utils,
)


class GrvtPerpetualWebUtilsTests(TestCase):
    def test_public_rest_url(self):
        self.assertEqual(
            "https://market-data.grvt.io/full/v1/ticker",
            web_utils.public_rest_url(CONSTANTS.TICKER_PATH_URL),
        )

    def test_private_rest_url(self):
        self.assertEqual(
            "https://trades.testnet.grvt.io/full/v1/order",
            web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=CONSTANTS.TESTNET_DOMAIN),
        )

    def test_edge_rest_url(self):
        self.assertEqual(
            "https://edge.testnet.grvt.io/auth/api_key/login",
            web_utils.edge_rest_url(CONSTANTS.AUTH_PATH_URL, domain=CONSTANTS.TESTNET_DOMAIN),
        )

    def test_wss_urls(self):
        self.assertEqual("wss://market-data.grvt.io/ws/full", web_utils.public_wss_url())
        self.assertEqual("wss://trades.testnet.grvt.io/ws/full", web_utils.private_wss_url(CONSTANTS.TESTNET_DOMAIN))


class GrvtPerpetualWebUtilsAsyncTests(IsolatedAsyncioTestCase):
    async def test_get_current_server_time(self):
        rest_assistant = AsyncMock()
        rest_assistant.execute_request = AsyncMock(return_value={"server_time": 1772159636314})
        api_factory = AsyncMock()
        api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)

        with patch.object(
            web_utils,
            "build_api_factory_without_time_synchronizer_pre_processor",
            return_value=api_factory,
        ):
            server_time = await web_utils.get_current_server_time()

        self.assertEqual(1772159636314.0, server_time)
        rest_assistant.execute_request.assert_awaited_once()
