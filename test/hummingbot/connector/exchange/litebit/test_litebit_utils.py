import unittest

from hummingbot.connector.exchange.litebit import litebit_utils as utils


class LitebitUtilTestCases(unittest.TestCase):

    def test_is_exchange_information_valid(self):
        invalid_info_1 = {
            "status": "maintenance",
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_1))

        invalid_info_2 = {
            "status": "active",
        }

        self.assertTrue(utils.is_exchange_information_valid(invalid_info_2))
