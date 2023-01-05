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
