import unittest
import asyncio
import time
from timeit import default_timer as timer

from hummingbot.core.utils.asyncio_throttle import Throttler, ThrottlerContextManager

class AsyncioThrottleTest(unittest.TestCase):
    def setUp(self):
        self.throttler = Throttler(rate_limit=(20, 1.1))
        self.loop = asyncio.get_event_loop()

    async def task(self, task_id, weight):
        async with self.throttler.weighted_task(weight):
            print(int(time.time()), f"Cat {task_id}: Meow {weight}")

    def test_tasks_complete_without_delay_when_throttle_below_rate_limit(self):
        tasks = [self.task(1, 5), self.task(3, 5), self.task(3, 5), self.task(4, 4)]
        start = timer()
        self.loop.run_until_complete(asyncio.gather(*tasks))
        end = timer()
        self.assertLess((end - start), 1.0)

    def test_tasks_complete_with_delay_when_throttle_above_rate_limit(self):
        tasks = [self.task(1, 5), self.task(3, 5), self.task(3, 5), self.task(4, 6)]
        start = timer()
        self.loop.run_until_complete(asyncio.gather(*tasks))
        end = timer()
        self.assertGreater((end - start), 1.0)

    def test_retry_interval_in_between_throttle_limits(self):
        current_retry_interval = self.throttler._retry_interval
        self.throttler._retry_interval = 3.0
        try:
            async def task_with_connection_lag(task_id, weight):
                async with self.throttler.weighted_task(weight):
                    print(int(time.time()), f"Cat {task_id}: Meow {weight}")
                    await asyncio.sleep(1)

            tasks = [task_with_connection_lag(1, 5),
                     task_with_connection_lag(3, 5),
                     task_with_connection_lag(3, 5),
                     task_with_connection_lag(4, 6),
                     task_with_connection_lag(5, 1)]

            start = timer()
            self.loop.run_until_complete(asyncio.gather(*tasks))
            end = timer()
            self.assertGreater((end - start), 2.0)
        except Exception as e:
            raise e
        finally:
            self.throttler._retry_interval = current_retry_interval
