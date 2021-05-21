"""
Unit tests for hummingbot.core.utils.async_retry
"""

import asyncio
from hummingbot.core.utils.async_retry import AllTriesFailedException, async_retry
import unittest


class FooException(Exception):
    """
    foo_three_times throws this exception, and we set async_retry to use this to trigger a retry
    """
    pass


class BarException(Exception):
    """
    bar_three_times throws this exception, but we do not set async_retry to use this to trigger a retry
    """
    pass


foo_counter = 0
bar_counter = 0


@async_retry(3, exception_types=[FooException], raise_exp=True, retry_interval=0)
async def foo_three_times(target):
    """
    This function runs three times. It raises FooException when the target is not met.
    When FooException is called, async_retry increments a counter and logs the error,
    if the counter is three and foo_three_times still fails, then it will raise
    AllTriesFailedException.
    """
    global foo_counter  # using a global variable makes running the tests easier
    if foo_counter >= target:
        return foo_counter
    else:
        foo_counter += 1
        raise FooException


@async_retry(3, raise_exp=False, retry_interval=0)
async def bar_three_times(target):
    """
    This function runs three times. It raises BarException when the target is not met.
    When FooException is called, async_retry increments a counter, if the counter is
    three and foo_three_times still fails, then it will raise AllTriesFailedException.
    """
    global bar_counter  # using a global variable makes running the tests easier
    if bar_counter >= target:
        return bar_counter
    else:
        bar_counter += 1
        raise BarException


class AsyncRetryTest(unittest.TestCase):
    def test_async_retry(self):
        """
        Unit tests for async_retry.
        """
        global foo_counter
        global bar_counter

        # run foo_three_times successfully
        foo_counter = 0
        foo_result = asyncio.get_event_loop().run_until_complete(foo_three_times(2))
        self.assertEqual(foo_result, 2)

        # pass a target to foo_three_times that it won't reach. This should raise the error from async_retry.
        foo_counter = 0
        self.assertRaises(AllTriesFailedException, asyncio.get_event_loop().run_until_complete, foo_three_times(5))

        # bar_three_times has raise_exp=False on async_retry. It will return None instead of raising an exception if
        # it fails to meet its condition in the three tries.
        # First run it in a case that passes.
        bar_counter = 0
        bar_result = asyncio.get_event_loop().run_until_complete(bar_three_times(2))
        self.assertEqual(bar_result, 2)

        # run bar_three_times so that it does not meet its expected conditions. It will not raise an error.
        bar_counter = 0
        bar_result = asyncio.get_event_loop().run_until_complete(bar_three_times(5))
        self.assertEqual(bar_result, None)
