import unittest
import asyncio
import time
from mock import patch
from hummingbot.core.utils.asyncio_throttle import Throttler


class AsyncioThrottleTest(unittest.TestCase):
    def setUp(self):
        self.retry_interval = -1
        self.throttler = Throttler(rate_limit=(20, 1), period_safety_margin=0, retry_interval=self.retry_interval)
        self.loop = asyncio.get_event_loop()

    async def task(self, task_id, weight):
        async with self.throttler.weighted_task(weight):
            print(int(time.time()), f"Cat {task_id}: Meow {weight}")

    @patch("hummingbot.core.utils.asyncio_throttle.ThrottlerContextManager._sleep")
    def test_tasks_complete_without_delay_when_throttle_below_rate_limit(self, sleep_mock):
        tasks = [self.task(1, 5), self.task(3, 5), self.task(3, 5), self.task(4, 4)]
        self.loop.run_until_complete(asyncio.gather(*tasks))
        for call_args in sleep_mock.call_args_list:
            self.assertNotIn(self.retry_interval, call_args.args)

    @patch("hummingbot.core.utils.asyncio_throttle.ThrottlerContextManager._sleep")
    def test_tasks_complete_with_delay_when_throttle_above_rate_limit(self, sleep_mock):
        tasks = [self.task(1, 5), self.task(3, 5), self.task(3, 5), self.task(4, 6)]
        self.loop.run_until_complete(asyncio.gather(*tasks))
        for call_args in sleep_mock.call_args_list:
            self.assertNotIn(self.retry_interval, call_args.args)
