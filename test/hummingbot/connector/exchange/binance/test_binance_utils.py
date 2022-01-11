import os
import socket
import time
import unittest
from unittest.mock import patch

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS
from hummingbot.connector.exchange.binance import binance_utils as utils


class BinanceUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def test_public_rest_url(self):
        path_url = "/TEST_PATH"
        domain = "com"
        expected_url = CONSTANTS.REST_URL.format(domain) + CONSTANTS.PUBLIC_API_VERSION + path_url
        self.assertEqual(expected_url, utils.public_rest_url(path_url, domain))

    def test_private_rest_url(self):
        path_url = "/TEST_PATH"
        domain = "com"
        expected_url = CONSTANTS.REST_URL.format(domain) + CONSTANTS.PRIVATE_API_VERSION + path_url
        self.assertEqual(expected_url, utils.private_rest_url(path_url, domain))

    def test_is_exchange_information_valid(self):
        invalid_info_1 = {
            "status": "BREAK",
            "permissions": ["MARGIN"],
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_1))

        invalid_info_2 = {
            "status": "BREAK",
            "permissions": ["SPOT"],
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_2))

        invalid_info_3 = {
            "status": "TRADING",
            "permissions": ["MARGIN"],
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_3))

        invalid_info_4 = {
            "status": "TRADING",
            "permissions": ["SPOT"],
        }

        self.assertTrue(utils.is_exchange_information_valid(invalid_info_4))

    @patch("hummingbot.connector.exchange.binance.binance_utils.get_tracking_nonce")
    def test_client_order_id_generation(self, nonce_mock):
        nonce = int(time.time() * 1e6)
        nonce_mock.return_value = nonce
        client_instance_id = hex(abs(hash(f"{socket.gethostname()}{os.getpid()}")))[2:6]

        client_order_id = utils.get_new_client_order_id(is_buy=True, trading_pair=self.hb_trading_pair)
        expected_id = (f"{CONSTANTS.HBOT_ORDER_ID_PREFIX}-{'B'}"
                       f"{self.base_asset[0]}{self.base_asset[-1]}{self.quote_asset[0]}{self.quote_asset[-1]}"
                       f"{client_instance_id}{nonce}")
        self.assertEqual(expected_id, client_order_id)

        client_order_id = utils.get_new_client_order_id(is_buy=False, trading_pair=self.hb_trading_pair)
        expected_id = (f"{CONSTANTS.HBOT_ORDER_ID_PREFIX}-{'S'}"
                       f"{self.base_asset[0]}{self.base_asset[-1]}{self.quote_asset[0]}{self.quote_asset[-1]}"
                       f"{client_instance_id}{nonce}")
        self.assertEqual(expected_id, client_order_id)
