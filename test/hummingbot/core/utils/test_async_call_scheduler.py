import asyncio
import time
import unittest
from unittest.mock import patch

from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler, AsyncCallSchedulerItem


class TestAsyncCallScheduler(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    _main_loop: asyncio.AbstractEventLoop
    _ev_loop: asyncio.AbstractEventLoop

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # This to mitigate the amount of work needed to clean all the mis-use of the Main event loop
        cls._main_loop = asyncio.get_event_loop()
        cls._ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls._ev_loop)
        cls.data_source = AsyncCallScheduler()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._ev_loop.stop()
        cls._ev_loop.close()
        asyncio.set_event_loop(cls._main_loop)
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)  # type: ignore

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and message in record.getMessage()
                   for record in self.log_records)

    @staticmethod
    async def sleep_2x_coroutine(*, x: float, delay: float = 1):
        await asyncio.sleep(delay)
        return x * 2

    @staticmethod
    async def sleep_2x_coroutine_with_exception(*, delay: float = 1):
        await asyncio.sleep(delay)
        raise ValueError("An error occurred")

    @staticmethod
    def slow_function(x: float, delay: float = 1):
        import time
        time.sleep(delay)
        return x * 3

    async def _async_test_helper(self, acs):
        async def dummy_coro():
            return True

        class AsyncCallSchedulerItemMock(AsyncCallSchedulerItem):
            futures_loop = []

            def __call__(self, *args, **kwargs):
                future = kwargs["future"]
                self.futures_loop.append(future._loop)
                return AsyncCallSchedulerItem(*args, **kwargs)

        # Replace the AsyncCallSchedulerItem class with the mocked version
        with unittest.mock.patch("hummingbot.core.utils.async_call_scheduler.AsyncCallSchedulerItem",
                                 AsyncCallSchedulerItemMock):
            # Test schedule_async_call
            result = await acs.schedule_async_call(dummy_coro(), timeout_seconds=1)
            self.assertEqual(result, True)

            # Test call_async
            result = await acs.call_async(lambda: True, timeout_seconds=1)
            self.assertEqual(result, True)

        return AsyncCallSchedulerItemMock.futures_loop

    def test_schedule_async_call(self):
        async def async_test_schedule_async_call():
            acs = AsyncCallScheduler()

            coro = self.sleep_2x_coroutine(x=2, delay=0.1)
            result = await acs.schedule_async_call(coro, timeout_seconds=0.2)

            self.assertEqual(result, 4, "The scheduled coroutine did not return the expected result")

        asyncio.run(async_test_schedule_async_call())

    def test_call_async(self):
        async def async_test_call_async():
            acs = AsyncCallScheduler()

            result = await acs.call_async(self.slow_function, 2, timeout_seconds=3)

            self.assertEqual(result, 6, "The call_async method did not return the expected result")

        asyncio.run(async_test_call_async())

    def test_schedule_async_call_with_exception(self):
        async def async_test_integration():
            acs = AsyncCallScheduler()

            # Schedule 3 coroutines with different timeouts
            fut1 = acs.schedule_async_call(self.sleep_2x_coroutine(x=1), timeout_seconds=3)
            fut2 = acs.schedule_async_call(self.sleep_2x_coroutine(x=2), timeout_seconds=2)
            fut3 = acs.schedule_async_call(self.sleep_2x_coroutine(x=3, delay=4), timeout_seconds=1)
            fut4 = acs.schedule_async_call(self.sleep_2x_coroutine_with_exception(), timeout_seconds=2)

            results = await asyncio.gather(fut1, fut2, fut3, fut4, return_exceptions=True)

            self.assertEqual(results[0], 2, "Coroutine 1 did not return the expected result")
            self.assertEqual(results[1], 4, "Coroutine 2 did not return the expected result")
            self.assertEqual(type(results[2]), type(asyncio.TimeoutError()), "Coroutine 3 did not raise a TimeoutError")
            self.assertIsInstance(type(results[3]), type(ValueError), "Coroutine 4 should have raised a ValueError")

        asyncio.run(async_test_integration())

    def test_test_stop_and_restart(self):
        async def async_test_stop_and_restart():
            acs = AsyncCallScheduler()
            acs.start()

            fut1 = acs.schedule_async_call(self.sleep_2x_coroutine(x=1), timeout_seconds=3)
            result1 = await fut1
            self.assertEqual(result1, 2, "Coroutine 1 did not return the expected result")

            acs.stop()
            fut2 = acs.schedule_async_call(self.sleep_2x_coroutine(x=2), timeout_seconds=3)
            result2 = await fut2
            self.assertEqual(result2, 4,
                             "Coroutine 2 did not return the expected result after restarting the scheduler")

            acs.start()
            fut3 = acs.schedule_async_call(self.sleep_2x_coroutine(x=3), timeout_seconds=3)
            result3 = await fut3
            self.assertEqual(result3, 6,
                             "Coroutine 3 did not return the expected result after restarting the scheduler")

        asyncio.run(async_test_stop_and_restart())

    def test_coro_scheduler_in_timeout(self):
        async def async_test_coro_scheduler():
            acs = AsyncCallScheduler()
            delay: float = 0.5
            number: float = 1.0
            expected: float = number * 2

            # Schedule coroutines with different timeouts, exceptions, and intervals
            coro_queue = acs.coro_queue
            coro = self.sleep_2x_coroutine(x=1, delay=delay)

            fut = asyncio.get_event_loop().create_future()

            coro_queue.put_nowait((fut, coro, delay + 0.1, "Coroutine Error"))

            # Start the _coro_scheduler with a custom interval
            scheduler = asyncio.create_task(acs._coro_scheduler(coro_queue, interval=delay / 1.5))

            try:
                # Set a timeout to prevent the test from blocking indefinitely
                results = await asyncio.wait_for(asyncio.gather(fut, return_exceptions=True), timeout=delay * 1.5)
            except asyncio.TimeoutError:
                results = [fut]
            finally:
                # Cancel the _coro_scheduler task
                scheduler.cancel()
                await asyncio.gather(scheduler, return_exceptions=True)

            if not fut.cancelled():
                self.assertEqual(results[0], expected, "Coroutine 1 did not return the expected result")
            else:
                self.fail("The future was cancelled unexpectedly")

        asyncio.run(async_test_coro_scheduler())

    def test_coro_scheduler_out_timeout(self):
        async def async_test_coro_scheduler():
            acs = AsyncCallScheduler()
            delay: float = 0.5
            timeout: float = delay - 0.1

            # Schedule coroutines with different timeouts, exceptions, and intervals
            coro_queue = acs.coro_queue
            coro = self.sleep_2x_coroutine(x=1, delay=delay)

            fut = asyncio.get_event_loop().create_future()

            coro_queue.put_nowait((fut, coro, timeout, "Coroutine Error"))

            # Start the _coro_scheduler with a custom interval
            scheduler = asyncio.create_task(acs._coro_scheduler(coro_queue, interval=delay / 1.5))

            try:
                # Set a timeout to prevent the test from blocking indefinitely
                results = await asyncio.wait_for(asyncio.gather(fut, return_exceptions=True), timeout=delay * 1.5)
            except asyncio.TimeoutError:
                results = [fut]
            finally:
                # Cancel the _coro_scheduler task
                scheduler.cancel()
                await asyncio.gather(scheduler, return_exceptions=True)

            if not fut.cancelled():
                self.assertEqual(type(results[0]), type(asyncio.TimeoutError()),
                                 "Coroutine did not raise a TimeoutError")
            else:
                self.fail("The future was cancelled unexpectedly")

        asyncio.run(async_test_coro_scheduler())

    def test_coro_scheduler_coro_exception(self):
        async def async_test_coro_scheduler():
            acs = AsyncCallScheduler()
            delay: float = 0.5
            timeout: float = delay + 0.1

            # Schedule coroutines with different timeouts, exceptions, and intervals
            coro_queue = acs.coro_queue
            coro = self.sleep_2x_coroutine_with_exception(delay=delay)

            fut = asyncio.get_event_loop().create_future()

            coro_queue.put_nowait((fut, coro, timeout, "Coroutine Error"))

            # Start the _coro_scheduler with a custom interval
            scheduler = asyncio.create_task(acs._coro_scheduler(coro_queue, interval=delay / 1.5))

            try:
                # Set a timeout to prevent the test from blocking indefinitely
                results = await asyncio.wait_for(asyncio.gather(fut, return_exceptions=True), timeout=delay * 1.5)
            except asyncio.TimeoutError:
                results = [fut]
            finally:
                # Cancel the _coro_scheduler task
                scheduler.cancel()
                await asyncio.gather(scheduler, return_exceptions=True)
                await asyncio.sleep(0.1)  # Add a small sleep to allow the log message to be emitted

            if not fut.cancelled():
                self.assertEqual(type(results[0]), ValueError, "Coroutine 4 should have raised a ValueError")
            else:
                self.fail("The future was cancelled unexpectedly")

        asyncio.run(async_test_coro_scheduler())

    def test_coro_scheduler_logging_message_on_timeout(self):
        async def async_test_logging_message():
            acs = AsyncCallScheduler()
            delay: float = 0.5
            timeout: float = delay - 0.1
            error_message: str = "Coroutine Timeout Error"

            # Schedule coroutines with different timeouts, exceptions, and intervals
            coro_queue = acs.coro_queue
            coro = self.sleep_2x_coroutine(x=1, delay=delay)

            fut = asyncio.get_event_loop().create_future()

            coro_queue.put_nowait((fut, coro, timeout, error_message))

            # Start the _coro_scheduler with a custom interval
            scheduler = asyncio.create_task(acs._coro_scheduler(coro_queue, interval=delay / 1.5))

            try:
                # Set a timeout to prevent the test from blocking indefinitely
                results = await asyncio.wait_for(asyncio.gather(fut, return_exceptions=True), timeout=delay * 1.5)
            except asyncio.TimeoutError:
                results = [fut]
            finally:
                # Cancel the _coro_scheduler task
                scheduler.cancel()
                await asyncio.gather(scheduler, return_exceptions=True)
                await asyncio.sleep(0.1)  # Add a small sleep to allow the log message to be emitted

            if not fut.cancelled():
                self.assertEqual(type(results[0]), type(asyncio.TimeoutError()),
                                 "Coroutine did not raise a TimeoutError")
            else:
                self.fail("The future was cancelled unexpectedly")

            self.assertTrue(self._is_logged("DEBUG", error_message))

        asyncio.run(async_test_logging_message())

    def test_coro_scheduler_gather_cases(self):
        async def async_test_coro_scheduler():
            acs = AsyncCallScheduler()

            # Schedule coroutines with different timeouts, exceptions, and intervals
            coro_queue = acs.coro_queue
            coro1 = self.sleep_2x_coroutine(x=1, delay=0.1)
            coro2 = self.sleep_2x_coroutine(x=2, delay=0.2)
            coro3 = self.sleep_2x_coroutine(x=3, delay=0.3)
            coro4 = self.sleep_2x_coroutine_with_exception(delay=0.4)

            fut1 = asyncio.get_event_loop().create_future()
            fut2 = asyncio.get_event_loop().create_future()
            fut3 = asyncio.get_event_loop().create_future()
            fut4 = asyncio.get_event_loop().create_future()

            coro_queue.put_nowait((fut1, coro1, 0.3))
            coro_queue.put_nowait((fut2, coro2, 0.3))
            coro_queue.put_nowait((fut3, coro3, 0.1))
            coro_queue.put_nowait((fut4, coro4, 0.2))

            # Start the _coro_scheduler with a custom interval
            scheduler = asyncio.create_task(acs._coro_scheduler(coro_queue, interval=0.1))
            results = []

            try:
                # Set a timeout to prevent the test from blocking indefinitely
                # TODO: This test is flaky, sometimes it fails with a TimeoutError
                # TODO: It maybe due to a future not returning when itself times-out
                await asyncio.wait_for(asyncio.gather(fut1,
                                                      fut2,
                                                      fut3,
                                                      fut4,
                                                      return_exceptions=True),
                                       timeout=1)
            except asyncio.TimeoutError:
                results = [fut1, fut2, fut3, fut4]
            finally:
                # Cancel the _coro_scheduler task
                scheduler.cancel()
                await asyncio.gather(scheduler, return_exceptions=True)

            self.assertEqual(len(results), 4, "The number of results does not match the number of futures")
            if not fut1.cancelled():
                self.assertEqual(fut1.result(), 2, "Coroutine 1 did not return the expected result")
            if not fut2.cancelled():
                self.assertEqual(fut2.result(), 4, "Coroutine 2 did not return the expected result")
            if not fut3.cancelled():
                self.assertIsInstance(fut3.result(), asyncio.TimeoutError, "Coroutine 3 did not raise a TimeoutError")
            if not fut4.cancelled():
                self.assertIsInstance(fut4.result(), ValueError, "Coroutine 4 should have raised a ValueError")

        asyncio.run(async_test_coro_scheduler())

    def test_coro_scheduler_sleep_exception(self):
        async def async_test_sleep_exception():
            acs = AsyncCallScheduler()
            delay: float = 0.5
            timeout: float = delay - 0.1

            coro_queue = acs.coro_queue
            coro = self.sleep_2x_coroutine(x=1, delay=delay)

            fut = asyncio.get_event_loop().create_future()

            coro_queue.put_nowait((fut, coro, timeout, "Coroutine Timeout Error"))

            # Mock asyncio.sleep to raise a custom exception
            async def sleep_side_effect(*args, **kwargs):
                raise Exception("Sleep failed")

            with patch("asyncio.sleep", side_effect=sleep_side_effect):
                scheduler = asyncio.create_task(acs._coro_scheduler(coro_queue, interval=delay / 1.5))

                try:
                    await asyncio.wait_for(asyncio.gather(fut, return_exceptions=True), timeout=delay * 1.5)
                except asyncio.TimeoutError:
                    pass
                finally:
                    scheduler.cancel()
                    await asyncio.gather(scheduler, return_exceptions=True)

            expected_message = "Scheduler sleep interrupted."

            self.assertTrue(self._is_logged("ERROR", expected_message))

        asyncio.run(async_test_sleep_exception())

    def test_methods_use_new_loop(self):
        num_loops = 5

        async def main():
            acs = AsyncCallScheduler()

            for _ in range(num_loops):
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                futures = await self._async_test_helper(acs)
                for future in futures:
                    self.assertEqual(future._loop, new_loop)

        asyncio.run(main())

    def test_multiple_event_loops(self):
        delay = 0.1
        num_loops = 5
        results = []

        async def main():
            acs = AsyncCallScheduler()

            for _ in range(num_loops):
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                results.append(await acs.call_async(self.slow_function, 2, delay, timeout_seconds=3 * delay))

            return results

        start_time = time.time()
        results = asyncio.run(main())
        elapsed_time = time.time() - start_time

        self.assertEqual(len(results), num_loops, "Not all event loops completed their tasks")
        self.assertTrue(all(result == 6 for result in results), "Incorrect result from coroutine")
        self.assertTrue(elapsed_time < 3 * delay * num_loops, "Test took too long to complete, possibly not running "
                                                              "concurrently")
