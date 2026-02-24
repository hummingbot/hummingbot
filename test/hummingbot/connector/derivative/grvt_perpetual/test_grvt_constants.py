from unittest import TestCase

from hummingbot.connector.derivative.grvt_perpetual import grvt_constants as CONSTANTS


class GrvtConstantsTests(TestCase):
    def test_exchange_name(self):
        self.assertEqual("grvt_perpetual", CONSTANTS.EXCHANGE_NAME)

    def test_rate_limits_defined(self):
        self.assertGreater(len(CONSTANTS.RATE_LIMITS), 5)
