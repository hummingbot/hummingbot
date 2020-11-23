import unittest
import asyncio
import time

from hummingbot.core.utils import async_ttl_cache


class AsyncTTLCacheUnitTest(unittest.TestCase):

    @async_ttl_cache(ttl=3, maxsize=1)
    async def get_timestamp(self):
        return time.time()

    def test_async_ttl_cache(self):
        ret_1 = asyncio.get_event_loop().run_until_complete(self.get_timestamp())
        ret_2 = asyncio.get_event_loop().run_until_complete(self.get_timestamp())
        self.assertEqual(ret_1, ret_2)
        time.sleep(2)
        ret_3 = asyncio.get_event_loop().run_until_complete(self.get_timestamp())
        self.assertEqual(ret_2, ret_3)
        time.sleep(2)
        ret_4 = asyncio.get_event_loop().run_until_complete(self.get_timestamp())
        self.assertGreater(ret_4, ret_3)
