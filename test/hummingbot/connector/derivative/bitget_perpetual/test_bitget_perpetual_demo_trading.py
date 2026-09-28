import asyncio
import unittest
from typing import Awaitable

from hummingbot.connector.derivative.bitget_perpetual import bitget_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bitget_perpetual import bitget_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_derivative import BitgetPerpetualDerivative
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_web_utils import (
    BitgetDemoTradingRESTPreProcessor,
)
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.data_feed.candles_feed.bitget_perpetual_candles import BitgetPerpetualDemoCandles
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig


class BitgetPerpetualDemoTradingTests(unittest.TestCase):
    """
    Bitget demo trading shares the mainnet REST host and is selected by a header, so
    every assertion here is about the header and the websocket host -- the two things
    that make a demo session actually reach the demo account.
    """

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def _request(self, url: str) -> RESTRequest:
        return RESTRequest(method=RESTMethod.GET, url=url)

    # --- URLs ---------------------------------------------------------------

    def test_demo_rest_url_is_the_mainnet_host(self):
        self.assertEqual(
            web_utils.public_rest_url(CONSTANTS.PUBLIC_TICKER_ENDPOINT, domain=CONSTANTS.DEFAULT_DOMAIN),
            web_utils.public_rest_url(CONSTANTS.PUBLIC_TICKER_ENDPOINT, domain=CONSTANTS.DEMO_DOMAIN),
        )

    def test_demo_websocket_host_differs_from_mainnet(self):
        mainnet = web_utils.public_ws_url(domain=CONSTANTS.DEFAULT_DOMAIN)
        demo = web_utils.public_ws_url(domain=CONSTANTS.DEMO_DOMAIN)

        self.assertTrue(mainnet.startswith("wss://ws.bitget.com"))
        self.assertTrue(demo.startswith("wss://wspap.bitget.com"))

    def test_demo_private_websocket_host_differs_from_mainnet(self):
        self.assertTrue(
            web_utils.private_ws_url(domain=CONSTANTS.DEMO_DOMAIN).startswith("wss://wspap.bitget.com")
        )

    # --- The demo header ----------------------------------------------------

    def test_pre_processor_marks_requests_as_demo(self):
        request = self._request(web_utils.public_rest_url(CONSTANTS.PUBLIC_TICKER_ENDPOINT))

        processed = self.async_run_with_timeout(BitgetDemoTradingRESTPreProcessor().pre_process(request))

        self.assertEqual("1", processed.headers[CONSTANTS.DEMO_TRADING_HEADER])

    def test_pre_processor_leaves_the_server_time_endpoint_alone(self):
        """Bitget answers 404 to /api/v2/public/time when the demo header is present."""
        request = self._request(web_utils.public_rest_url(CONSTANTS.PUBLIC_TIME_ENDPOINT))

        processed = self.async_run_with_timeout(BitgetDemoTradingRESTPreProcessor().pre_process(request))

        self.assertNotIn(CONSTANTS.DEMO_TRADING_HEADER, processed.headers or {})

    def test_pre_processor_keeps_existing_headers(self):
        request = self._request(web_utils.public_rest_url(CONSTANTS.PUBLIC_TICKER_ENDPOINT))
        request.headers = {"X-EXISTING": "kept"}

        processed = self.async_run_with_timeout(BitgetDemoTradingRESTPreProcessor().pre_process(request))

        self.assertEqual("kept", processed.headers["X-EXISTING"])
        self.assertEqual("1", processed.headers[CONSTANTS.DEMO_TRADING_HEADER])

    # --- Factory wiring -----------------------------------------------------

    def test_api_factory_adds_the_demo_pre_processor_only_for_the_demo_domain(self):
        demo = web_utils.build_api_factory(domain=CONSTANTS.DEMO_DOMAIN)
        mainnet = web_utils.build_api_factory(domain=CONSTANTS.DEFAULT_DOMAIN)

        self.assertTrue(
            any(isinstance(p, BitgetDemoTradingRESTPreProcessor) for p in demo._rest_pre_processors)
        )
        self.assertFalse(
            any(isinstance(p, BitgetDemoTradingRESTPreProcessor) for p in mainnet._rest_pre_processors)
        )

    # --- Connector ----------------------------------------------------------

    def _connector(self, domain: str) -> BitgetPerpetualDerivative:
        return BitgetPerpetualDerivative(
            bitget_perpetual_api_key="testKey",
            bitget_perpetual_secret_key="testSecret",
            bitget_perpetual_passphrase="testPassphrase",
            trading_pairs=["BTC-USDT"],
            trading_required=False,
            domain=domain,
        )

    def test_connector_reports_the_demo_name_and_domain(self):
        connector = self._connector(CONSTANTS.DEMO_DOMAIN)

        self.assertEqual(CONSTANTS.DEMO_DOMAIN, connector.name)
        self.assertEqual(CONSTANTS.DEMO_DOMAIN, connector.domain)

    def test_connector_defaults_to_mainnet(self):
        connector = BitgetPerpetualDerivative(
            bitget_perpetual_api_key="testKey",
            bitget_perpetual_secret_key="testSecret",
            bitget_perpetual_passphrase="testPassphrase",
            trading_pairs=["BTC-USDT"],
            trading_required=False,
        )

        self.assertEqual(CONSTANTS.EXCHANGE_NAME, connector.name)
        self.assertEqual(CONSTANTS.DEFAULT_DOMAIN, connector.domain)

    def test_demo_connector_websocket_urls_use_the_demo_host(self):
        connector = self._connector(CONSTANTS.DEMO_DOMAIN)

        order_book_url = connector._create_order_book_data_source()._ws_url()
        user_stream_url = connector._create_user_stream_data_source()._ws_url()

        self.assertTrue(order_book_url.startswith("wss://wspap.bitget.com"))
        self.assertTrue(user_stream_url.startswith("wss://wspap.bitget.com"))

    # --- Candles ------------------------------------------------------------

    def test_demo_candles_are_registered_under_the_demo_name(self):
        candles = CandlesFactory.get_candle(
            CandlesConfig(connector=CONSTANTS.DEMO_DOMAIN, trading_pair="BTC-USDT", interval="1m")
        )

        self.assertIsInstance(candles, BitgetPerpetualDemoCandles)

    def test_demo_candles_send_the_demo_header(self):
        candles = BitgetPerpetualDemoCandles(trading_pair="BTC-USDT")

        self.assertEqual({CONSTANTS.DEMO_TRADING_HEADER: "1"}, candles._get_rest_candles_headers())

    def test_demo_candles_name_is_distinct_from_mainnet(self):
        candles = BitgetPerpetualDemoCandles(trading_pair="BTC-USDT")

        self.assertEqual(f"{CONSTANTS.DEMO_DOMAIN}_BTC-USDT", candles.name)


if __name__ == "__main__":
    unittest.main()
