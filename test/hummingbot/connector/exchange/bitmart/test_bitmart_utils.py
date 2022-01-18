from unittest import TestCase
from unittest.mock import patch

# from hummingbot.connector.exchange.bitmart import bitmart_constants as CONSTANTS
from hummingbot.connector.exchange.bitmart import bitmart_utils as utils


class BitmartUtilsTests(TestCase):

    def test_trading_pair_convertion(self):
        hbot_trading_pair = "BTC-USDT"
        exchange_trading_pair = "BTC_USDT"
        self.assertEqual(exchange_trading_pair, utils.convert_to_exchange_trading_pair(hbot_trading_pair))
        self.assertEqual(hbot_trading_pair, utils.convert_from_exchange_trading_pair(exchange_trading_pair))

    @patch('hummingbot.connector.exchange.bitmart.bitmart_utils.get_tracking_nonce')
    def test_client_order_id_creation(self, nonce_provider_mock):
        nonce_provider_mock.return_value = 1000
        self.assertEqual("hummingbot-B-BTC-USDT-1000", utils.get_new_client_order_id(True, "BTC-USDT"))
