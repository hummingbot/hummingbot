from unittest import TestCase

from hummingbot.connector.exchange.btc_markets import btc_markets_utils as utils


class UtilsTest(TestCase):
    def test_is_exchange_information_valid(self):
        exchange_info = {
            "status": "Online"
        }
        valid = utils.is_exchange_information_valid(exchange_info=exchange_info)
        self.assertTrue(valid)

        exchange_info = {
            "status": "Post Only"
        }
        valid = utils.is_exchange_information_valid(exchange_info=exchange_info)
        self.assertTrue(valid)

        exchange_info = {
            "status": "Limit Only"
        }
        valid = utils.is_exchange_information_valid(exchange_info=exchange_info)
        self.assertTrue(valid)
