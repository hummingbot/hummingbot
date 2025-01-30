from unittest import TestCase

from hummingbot.connector.exchange.derive import derive_utils as utils


class DeriveUtilsTests(TestCase):
    pass

    def test_is_exchange_information_valid(self):
        invalid_info_1 = False,
        self.assertFalse(utils.is_exchange_information_valid(invalid_info_1))

        invalid_info_4 = True,

        self.assertTrue(utils.is_exchange_information_valid(invalid_info_4))
