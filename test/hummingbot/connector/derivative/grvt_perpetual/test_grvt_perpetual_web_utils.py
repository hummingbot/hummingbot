import unittest

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils as web_utils
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class GrvtPerpetualWebUtilsTest(unittest.TestCase):
    def test_public_rest_url_mainnet_market_data(self):
        url = web_utils.public_rest_url(CONSTANTS.ALL_INSTRUMENTS_URL)
        self.assertEqual(f"{CONSTANTS.MARKET_DATA_BASE_URL}{CONSTANTS.ALL_INSTRUMENTS_URL}", url)

    def test_public_rest_url_testnet_market_data(self):
        url = web_utils.public_rest_url(CONSTANTS.ALL_INSTRUMENTS_URL, domain=CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(f"{CONSTANTS.TESTNET_MARKET_DATA_BASE_URL}{CONSTANTS.ALL_INSTRUMENTS_URL}", url)

    def test_private_rest_url_mainnet_trade_data(self):
        url = web_utils.private_rest_url(CONSTANTS.CREATE_ORDER_URL)
        self.assertEqual(f"{CONSTANTS.TRADE_BASE_URL}{CONSTANTS.CREATE_ORDER_URL}", url)

    def test_private_rest_url_testnet_trade_data(self):
        url = web_utils.private_rest_url(CONSTANTS.CREATE_ORDER_URL, domain=CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(f"{CONSTANTS.TESTNET_TRADE_BASE_URL}{CONSTANTS.CREATE_ORDER_URL}", url)

    def test_edge_url_mainnet(self):
        url = web_utils.rest_url(CONSTANTS.AUTH_LOGIN_URL)
        self.assertEqual(f"{CONSTANTS.EDGE_BASE_URL}{CONSTANTS.AUTH_LOGIN_URL}", url)

    def test_edge_url_testnet(self):
        url = web_utils.rest_url(CONSTANTS.AUTH_LOGIN_URL, domain=CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(f"{CONSTANTS.TESTNET_EDGE_BASE_URL}{CONSTANTS.AUTH_LOGIN_URL}", url)

    def test_orderbook_routes_to_market_data(self):
        url = web_utils.rest_url(CONSTANTS.ORDERBOOK_URL)
        self.assertTrue(url.startswith(CONSTANTS.MARKET_DATA_BASE_URL))

    def test_ticker_routes_to_market_data(self):
        url = web_utils.rest_url(CONSTANTS.TICKER_URL)
        self.assertTrue(url.startswith(CONSTANTS.MARKET_DATA_BASE_URL))

    def test_cancel_order_routes_to_trade(self):
        url = web_utils.rest_url(CONSTANTS.CANCEL_ORDER_URL)
        self.assertTrue(url.startswith(CONSTANTS.TRADE_BASE_URL))

    def test_positions_routes_to_trade(self):
        url = web_utils.rest_url(CONSTANTS.POSITIONS_URL)
        self.assertTrue(url.startswith(CONSTANTS.TRADE_BASE_URL))

    def test_market_data_wss_url_mainnet(self):
        url = web_utils.market_data_wss_url()
        self.assertEqual(CONSTANTS.MARKET_WS_FULL_URL, url)

    def test_market_data_wss_url_testnet(self):
        url = web_utils.market_data_wss_url(domain=CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(CONSTANTS.TESTNET_MARKET_WS_FULL_URL, url)

    def test_trade_wss_url_mainnet(self):
        url = web_utils.trade_wss_url()
        self.assertEqual(CONSTANTS.TRADE_WS_FULL_URL, url)

    def test_trade_wss_url_testnet(self):
        url = web_utils.trade_wss_url(domain=CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(CONSTANTS.TESTNET_TRADE_WS_FULL_URL, url)

    def test_wss_url_defaults_to_market_data(self):
        url = web_utils.wss_url()
        self.assertEqual(web_utils.market_data_wss_url(), url)

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory()
        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)
        self.assertEqual(1, len(api_factory._rest_pre_processors))

    def test_build_api_factory_without_time_synchronizer(self):
        throttler = web_utils.create_throttler()
        api_factory = web_utils.build_api_factory_without_time_synchronizer_pre_processor(throttler)
        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

    def test_is_exchange_information_valid_active(self):
        instrument = {"instrument": "BTC_USDT_Perp", "is_active": True}
        self.assertTrue(web_utils.is_exchange_information_valid(instrument))

    def test_is_exchange_information_valid_inactive(self):
        instrument = {"instrument": "BTC_USDT_Perp", "is_active": False}
        self.assertFalse(web_utils.is_exchange_information_valid(instrument))

    def test_is_exchange_information_valid_default(self):
        instrument = {"instrument": "BTC_USDT_Perp"}
        self.assertTrue(web_utils.is_exchange_information_valid(instrument))
