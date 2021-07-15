import asyncio
import time
import unittest

from hummingbot.core.api_throttler.api_throttler_base import APIThrottlerBase
from hummingbot.core.api_throttler.api_request_context_base import APIRequestContextBase
from hummingbot.core.api_throttler.data_types import RateLimit, TaskLog

TEST_PATH_URL = "/hummingbot"


class MockAPIThrottler(APIThrottlerBase):
    def execute_task(self):
        return MockAPIRequestContext(
            task_logs=self._task_logs,
            rate_limit=self._path_rate_limit_map[TEST_PATH_URL]
        )


class MockAPIRequestContext(APIRequestContextBase):
    def within_capacity(self) -> bool:
        return len(self._task_logs) < 1


class APIRequestContextBaseUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        cls.rate_limit: RateLimit = RateLimit(limit=1.0,
                                              time_interval=5.0,
                                              path_url=TEST_PATH_URL)

    def setUp(self) -> None:
        super().setUp()
        self.throttler = MockAPIThrottler(rate_limit_list=[self.rate_limit])

    @staticmethod
    def simulate_throttler_getting_freed(throttler: APIThrottlerBase, path_url: str):
        while len(throttler._path_task_logs_map[path_url]) > 0:
            throttler._path_task_logs_map[path_url].popleft()

    def test_flush(self):

        # Test: No Task Logs to flush
        context = MockAPIRequestContext(self.throttler._path_task_logs_map[TEST_PATH_URL], self.rate_limit)
        context.flush()

        self.assertEqual(0, len(self.throttler._path_task_logs_map[TEST_PATH_URL]))

        # Test: Test that TaskLogs are being flushed accordingly.
        task_0 = TaskLog(timestamp=1.0, path_url=TEST_PATH_URL)
        task_1 = TaskLog(timestamp=time.time() + 60, path_url=TEST_PATH_URL)
        self.throttler._path_task_logs_map[TEST_PATH_URL].append(task_0)
        self.throttler._path_task_logs_map[TEST_PATH_URL].append(task_1)
        self.assertEqual(2, len(self.throttler._path_task_logs_map[TEST_PATH_URL]))

        context = MockAPIRequestContext(self.throttler._path_task_logs_map[TEST_PATH_URL], self.rate_limit)
        context.flush()
        self.assertEqual(1, len(self.throttler._path_task_logs_map[TEST_PATH_URL]))

    def test_within_capacity(self):
        # Test 1: Abstract Class cannot be instantiated
        with self.assertRaises(TypeError):
            context = APIRequestContextBase(self.throttler._path_task_logs_map[TEST_PATH_URL], self.rate_limit)
            context.within_capacity()

        # Test 2: Mock implementation of within_capacity
        context = MockAPIRequestContext(self.throttler._path_task_logs_map[TEST_PATH_URL], self.rate_limit)
        self.assertTrue(context.within_capacity())

    def test_task_appended_after_acquire(self):
        # Test 1: Task gets appended to task_logs
        context = MockAPIRequestContext(self.throttler._path_task_logs_map[TEST_PATH_URL], rate_limit=self.rate_limit)
        self.ev_loop.run_until_complete(context.acquire())

        self.assertEqual(1, len(self.throttler._path_task_logs_map[TEST_PATH_URL]))

    def test_acquire_awaits_when_exceed_capacity(self):
        # Test 1: Test acquire() awaiting when NOT within_capacity
        task = TaskLog(timestamp=time.time(), path_url=TEST_PATH_URL)
        self.throttler._path_task_logs_map[TEST_PATH_URL].append(task)

        context = MockAPIRequestContext(self.throttler._path_task_logs_map[TEST_PATH_URL], rate_limit=self.rate_limit)
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(context.acquire(), 1.0)
            )

        # Simulate throttler being freed and ready to take new task.
        self.simulate_throttler_getting_freed(self.throttler, TEST_PATH_URL)
        self.assertEqual(0, len(self.throttler._path_task_logs_map[TEST_PATH_URL]))

        # Test 2: Test acquire being able to take new tasks when within capacity
        self.ev_loop.run_until_complete(
            asyncio.wait_for(context.acquire(), 1.0)
        )
        self.assertEqual(1, len(self.throttler._path_task_logs_map[TEST_PATH_URL]))
