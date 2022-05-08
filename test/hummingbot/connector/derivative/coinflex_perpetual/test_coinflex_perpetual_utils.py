import time
import unittest

from mock import patch

import hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_utils as utils
import hummingbot.connector.derivative.coinflex_perpetual.constants as CONSTANTS


class CoinflexPerpetualUtilsUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def test_is_exchange_information_valid(self):
        invalid_info_1 = {
            "type": "MARGIN",
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_1))

        valid_info_1 = {
            "name": "XX Perp",
            "type": "FUTURE",
        }

        self.assertTrue(utils.is_exchange_information_valid(valid_info_1))

    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_utils.get_tracking_nonce")
    def test_client_order_id_generation(self, nonce_mock):
        nonce = int(time.time() * 1e6)
        nonce_mock.return_value = nonce

        client_order_id = utils.get_new_client_order_id(is_buy=True, trading_pair=self.hb_trading_pair)
        expected_id = (f"{CONSTANTS.HBOT_ORDER_ID_PREFIX}{'0'}"
                       f"{nonce}")
        self.assertEqual(expected_id, client_order_id)

        client_order_id = utils.get_new_client_order_id(is_buy=False, trading_pair=self.hb_trading_pair)
        expected_id = (f"{CONSTANTS.HBOT_ORDER_ID_PREFIX}{'1'}"
                       f"{nonce}")
        self.assertEqual(expected_id, client_order_id)
