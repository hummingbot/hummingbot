from unittest import TestCase
from unittest.mock import patch

from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS, ndax_utils as utils


class NdaxUtilsTests(TestCase):

    def test_trading_pair_convertion(self):
        trading_pair = "BTC-USDT"
        self.assertEqual("BTCUSDT", utils.convert_to_exchange_trading_pair(trading_pair))

    @patch('hummingbot.connector.exchange.ndax.ndax_utils.get_tracking_nonce')
    def test_client_order_id_creation(self, nonce_provider_mock):
        nonce_provider_mock.return_value = 1000
        self.assertEqual(f"{utils.HUMMINGBOT_ID_PREFIX}{1000}", utils.get_new_client_order_id(True, "BTC-USDT"))

    def test_rest_api_url(self):
        url = utils.rest_api_url(None)
        self.assertEqual(CONSTANTS.REST_URLS.get("ndax_main"), url)

        url = utils.rest_api_url("ndax_main")
        self.assertEqual(CONSTANTS.REST_URLS.get("ndax_main"), url)

        url = utils.rest_api_url("ndax_testnet")
        self.assertEqual(CONSTANTS.REST_URLS.get("ndax_testnet"), url)

    def test_wss_url(self):
        url = utils.wss_url(None)
        self.assertEqual(CONSTANTS.WSS_URLS.get("ndax_main"), url)

        url = utils.wss_url("ndax_main")
        self.assertEqual(CONSTANTS.WSS_URLS.get("ndax_main"), url)

        url = utils.wss_url("ndax_testnet")
        self.assertEqual(CONSTANTS.WSS_URLS.get("ndax_testnet"), url)
