import asyncio
import logging
import unittest
from unittest.mock import AsyncMock, MagicMock

from hummingbot.core.utils.async_utils import (
    call_sync,
    run_command,
    safe_ensure_future,
    safe_gather,
    safe_wrapper,
    wait_til,
)


class TestAsyncUtils(unittest.TestCase):
    ev_loop = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.ev_loop)

    def run_async(self, async_fn):
        return self.ev_loop.run_until_complete(async_fn)

    async def async_fn_success(self):
        return "success"

    def test_safe_wrapper_success(self):
        result = self.run_async(safe_wrapper(self.async_fn_success()))
        self.assertEqual(result, "success")

    async def async_fn_cancelled_error(self):
        raise asyncio.CancelledError()

    def test_safe_wrapper_cancelled_error(self):
        with self.assertRaises(asyncio.CancelledError):
            self.run_async(safe_wrapper(self.async_fn_cancelled_error()))

    async def async_fn_exception(self):
        raise Exception("error")

    def test_safe_wrapper_exception(self):
        with self.assertLogs(level=logging.ERROR) as log:
            self.run_async(safe_wrapper(self.async_fn_exception()))
        self.assertIn("Unhandled error in background task: error", log.records[0].message)

    def test_safe_ensure_future(self):
        future = safe_ensure_future(self.async_fn_success(), loop=self.ev_loop)
        result = self.run_async(future)
        self.assertEqual(result, "success")

    def test_safe_gather_success(self):
        async def async_fn():
            return "success"

        result = self.run_async(safe_gather(async_fn()))
        self.assertEqual(result, ["success"])

    def test_safe_gather_exception(self):
        async def async_fn():
            raise Exception("error")

        with self.assertRaises(Exception):
            self.run_async(safe_gather(async_fn()))

    def test_wait_til_success(self):
        condition = MagicMock(return_value=True)

        self.run_async(wait_til(condition))

        condition.assert_called_once()

    def test_wait_til_timeout(self):
        condition = MagicMock(return_value=False)

        with self.assertRaises(Exception):
            self.run_async(wait_til(condition, timeout=0.1))

    def test_run_command(self):
        stdout = "command output"
        process = MagicMock()
        process.communicate.return_value = (stdout.encode(), None)
        asyncio.create_subprocess_shell = AsyncMock(return_value=process)

        result = self.run_async(run_command("echo", "hello"))

        self.assertEqual(result, "hello")

    async def async_fn_timeout(self):
        await asyncio.sleep(1)

    def test_call_sync_success(self):
        loop = asyncio.get_event_loop()
        result = call_sync(self.async_fn_success(), loop)
        self.assertEqual(result, "success")

    def test_call_sync_timeout(self):
        loop = asyncio.get_event_loop()
        with self.assertRaises(asyncio.TimeoutError):
            call_sync(self.async_fn_timeout(), loop, timeout=0.1)


if __name__ == "__main__":
    unittest.main()
