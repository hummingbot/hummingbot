import os
import socket
import unittest

from mock import patch

import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils as utils
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils import BROKER_ID


class BinancePerpetualUtilsUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils.get_tracking_nonce")
    def test_get_client_order_id(self, mock_nonce):
        mock_nonce.return_value = int("1" * 16)
        client_instance_id = hex(abs(hash(f"{socket.gethostname()}{os.getpid()}")))[2:6]

        result = utils.get_client_order_id("buy", self.trading_pair)

        expected_client_order_id = f"{BROKER_ID}-BCAHT{client_instance_id}{int('1'*16)}"

        self.assertEqual(result, expected_client_order_id)
