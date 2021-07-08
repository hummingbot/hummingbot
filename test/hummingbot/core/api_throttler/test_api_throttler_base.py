import unittest

from hummingbot.core.api_throttler.api_throttler_base import APIThrottlerBase
from hummingbot.core.api_throttler.data_types import RateLimit


class MockAPIThrottler(APIThrottlerBase):

    def execute_task(self):
        return id(self)


class APIThrotterBaseUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.rate_limit: RateLimit = RateLimit(1, 1)
        cls.throttler = APIThrottlerBase(rate_limit_list=[cls.rate_limit])

    def test_execute_task(self):

        # Test 1: Abstract method not implemented
        with self.assertRaises(NotImplementedError):
            self.throttler.execute_task()

        # Test 2: Mock implementation of execute_task
        throttler = MockAPIThrottler([self.rate_limit])
        self.assertEqual(id(throttler), throttler.execute_task())
