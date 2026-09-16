import asyncio
import time
import unittest
from unittest.mock import patch

from hummingbot.core.api_throttler.async_request_context_base import AsyncRequestContextBase
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.data_types import RateLimit, TaskLog

LIMIT_ID = "test_limit"


class InFlightAccountingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.rate_limit = RateLimit(limit_id=LIMIT_ID, limit=1, time_interval=1)
        self.throttler = AsyncThrottler(rate_limits=[self.rate_limit], retry_interval=0.001)

    def tearDown(self) -> None:
        self.loop.close()

    def _context(self):
        return self.throttler.execute_task(limit_id=LIMIT_ID)

    def _log(self, age: float, completed: bool) -> TaskLog:
        return TaskLog(timestamp=time.time() - age, rate_limit=self.rate_limit,
                       weight=1, completed=completed)

    def test_task_log_defaults_to_completed(self):
        # Task logs created outside a request should work the same as before.
        self.assertTrue(TaskLog(timestamp=0, rate_limit=self.rate_limit, weight=1).completed)

    def test_a_finished_request_frees_its_slot_once_the_window_passes(self):
        context = self._context()
        self.throttler._task_logs.append(self._log(age=5, completed=True))

        context.flush()

        self.assertEqual([], self.throttler._task_logs)

    def test_an_outstanding_request_keeps_its_slot_past_the_window(self):
        context = self._context()
        self.throttler._task_logs.append(self._log(age=5, completed=False))

        context.flush()

        self.assertEqual(1, len(self.throttler._task_logs))
        self.assertFalse(context.within_capacity())

    def test_the_hold_is_bounded_so_a_lost_task_cannot_wedge_the_limit(self):
        context = self._context()
        # A task that was never marked complete, e.g. cancelled before entering the context.
        self.throttler._task_logs.append(
            self._log(age=AsyncRequestContextBase.IN_FLIGHT_HOLD_LIMIT + 1, completed=False)
        )

        context.flush()

        self.assertEqual([], self.throttler._task_logs)
        self.assertTrue(context.within_capacity())

    def test_slot_is_released_when_the_request_raises(self):
        async def scenario():
            with self.assertRaises(RuntimeError):
                async with self._context():
                    raise RuntimeError("request blew up")
            return list(self.throttler._task_logs)

        logs = self.loop.run_until_complete(scenario())

        self.assertTrue(all(task.completed for task in logs))

    def test_slot_is_released_on_normal_exit(self):
        async def scenario():
            async with self._context():
                outstanding = [t.completed for t in self.throttler._task_logs]
            return outstanding, [t.completed for t in self.throttler._task_logs]

        during, after = self.loop.run_until_complete(scenario())

        self.assertEqual([False], during)
        self.assertEqual([True], after)

    def test_concurrency_is_capped_for_requests_slower_than_the_window(self):
        # Limit of 2 per second, and each request takes much longer than a second.
        throttler = AsyncThrottler(
            rate_limits=[RateLimit(limit_id=LIMIT_ID, limit=2, time_interval=1)],
            retry_interval=0.001,
        )
        peak = 0
        in_flight = 0

        async def request():
            nonlocal peak, in_flight
            async with throttler.execute_task(limit_id=LIMIT_ID):
                in_flight += 1
                peak = max(peak, in_flight)
                await asyncio.sleep(5)
                in_flight -= 1

        async def scenario():
            tasks = [asyncio.create_task(request()) for _ in range(20)]
            await asyncio.sleep(1.5)  # long enough for the window to pass
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        with patch("hummingbot.logger.logger.HummingbotLogger.notify", lambda *a, **k: None):
            self.loop.run_until_complete(scenario())

        self.assertEqual(2, peak)


if __name__ == "__main__":
    unittest.main()
