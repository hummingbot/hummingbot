from hummingbot.core.api_throttler.data_types import CallRateLimit

import unittest


class CallRateLimitUnitTest(unittest.TestCase):

    def test_call_rate_limit(self):
        limit: CallRateLimit = CallRateLimit(limit_id="A", limit=100, time_interval=10.)
        self.assertEqual("A", limit.limit_id)
        self.assertEqual(100, limit.limit)
        self.assertEqual(10., limit.time_interval)
        self.assertEqual(1, limit.weight)
        self.assertEqual(0.5, limit.period_safety_margin)
        self.assertEqual("limit_id: A, limit: 100, time interval: 10.0, weight: 1, period_safety_margin: 0.5",
                         str(limit))
