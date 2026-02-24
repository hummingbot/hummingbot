from unittest import TestCase

from hummingbot.connector.derivative.grvt_perpetual import grvt_constants as CONSTANTS


class GrvtRateLimitSanityTests(TestCase):
    def test_all_limits_have_ids(self):
        for rl in CONSTANTS.RATE_LIMITS:
            self.assertTrue(getattr(rl, "limit_id", None))
