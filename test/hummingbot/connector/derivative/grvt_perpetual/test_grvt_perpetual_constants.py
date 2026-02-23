import unittest

from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.in_flight_order import OrderState


class GrvtPerpetualConstantsTests(unittest.TestCase):
    def test_exchange_name(self):
        self.assertEqual("grvt_perpetual", CONSTANTS.EXCHANGE_NAME)

    def test_domain(self):
        self.assertEqual(CONSTANTS.EXCHANGE_NAME, CONSTANTS.DOMAIN)

    def test_testnet_domain(self):
        self.assertEqual("grvt_perpetual_testnet", CONSTANTS.TESTNET_DOMAIN)

    def test_base_urls_are_https(self):
        self.assertTrue(CONSTANTS.EDGE_BASE_URL.startswith("https://"))
        self.assertTrue(CONSTANTS.TRADE_BASE_URL.startswith("https://"))
        self.assertTrue(CONSTANTS.MARKET_DATA_BASE_URL.startswith("https://"))
        self.assertTrue(CONSTANTS.TESTNET_EDGE_BASE_URL.startswith("https://"))
        self.assertTrue(CONSTANTS.TESTNET_TRADE_BASE_URL.startswith("https://"))
        self.assertTrue(CONSTANTS.TESTNET_MARKET_DATA_BASE_URL.startswith("https://"))

    def test_websocket_urls_are_wss(self):
        self.assertTrue(CONSTANTS.MARKET_WS_URL.startswith("wss://"))
        self.assertTrue(CONSTANTS.TRADE_WS_URL.startswith("wss://"))
        self.assertTrue(CONSTANTS.MARKET_WS_FULL_URL.startswith("wss://"))
        self.assertTrue(CONSTANTS.TRADE_WS_FULL_URL.startswith("wss://"))
        self.assertTrue(CONSTANTS.TESTNET_MARKET_WS_URL.startswith("wss://"))
        self.assertTrue(CONSTANTS.TESTNET_TRADE_WS_URL.startswith("wss://"))

    def test_chain_ids(self):
        self.assertEqual(325, CONSTANTS.MAINNET_CHAIN_ID)
        self.assertEqual(326, CONSTANTS.TESTNET_CHAIN_ID)

    def test_price_precision(self):
        self.assertEqual(10**9, CONSTANTS.PRICE_PRECISION)

    def test_order_state_mapping(self):
        self.assertEqual(OrderState.PENDING_CREATE, CONSTANTS.ORDER_STATE["PENDING"])
        self.assertEqual(OrderState.OPEN, CONSTANTS.ORDER_STATE["OPEN"])
        self.assertEqual(OrderState.FILLED, CONSTANTS.ORDER_STATE["FILLED"])
        self.assertEqual(OrderState.FAILED, CONSTANTS.ORDER_STATE["REJECTED"])
        self.assertEqual(OrderState.CANCELED, CONSTANTS.ORDER_STATE["CANCELLED"])

    def test_rate_limits_not_empty(self):
        self.assertGreater(len(CONSTANTS.RATE_LIMITS), 0)

    def test_heartbeat_interval(self):
        self.assertEqual(30.0, CONSTANTS.HEARTBEAT_TIME_INTERVAL)

    def test_instrument_suffix(self):
        self.assertEqual("_Perp", CONSTANTS.INSTRUMENT_SUFFIX)

    def test_currency(self):
        self.assertEqual("USDT", CONSTANTS.CURRENCY)

    def test_endpoint_paths_start_with_slash(self):
        endpoints = [
            CONSTANTS.AUTH_LOGIN_URL,
            CONSTANTS.ALL_INSTRUMENTS_URL,
            CONSTANTS.ORDERBOOK_URL,
            CONSTANTS.TICKER_URL,
            CONSTANTS.RECENT_TRADES_URL,
            CONSTANTS.FUNDING_RATE_URL,
            CONSTANTS.CREATE_ORDER_URL,
            CONSTANTS.CANCEL_ORDER_URL,
            CONSTANTS.CANCEL_ALL_ORDERS_URL,
            CONSTANTS.OPEN_ORDERS_URL,
            CONSTANTS.ORDER_URL,
            CONSTANTS.FILL_HISTORY_URL,
            CONSTANTS.POSITIONS_URL,
            CONSTANTS.ACCOUNT_SUMMARY_URL,
            CONSTANTS.FUNDING_PAYMENT_HISTORY_URL,
        ]
        for endpoint in endpoints:
            self.assertTrue(endpoint.startswith("/"), f"Endpoint {endpoint} does not start with /")

    def test_aliases_point_to_correct_endpoints(self):
        self.assertEqual(CONSTANTS.TICKER_URL, CONSTANTS.TICKER_PRICE_CHANGE_URL)
        self.assertEqual(CONSTANTS.ORDERBOOK_URL, CONSTANTS.SNAPSHOT_REST_URL)
        self.assertEqual(CONSTANTS.ALL_INSTRUMENTS_URL, CONSTANTS.EXCHANGE_INFO_URL)
        self.assertEqual(CONSTANTS.FILL_HISTORY_URL, CONSTANTS.ACCOUNT_TRADE_LIST_URL)
        self.assertEqual(CONSTANTS.ACCOUNT_SUMMARY_URL, CONSTANTS.ACCOUNT_INFO_URL)
        self.assertEqual(CONSTANTS.POSITIONS_URL, CONSTANTS.POSITION_INFORMATION_URL)
