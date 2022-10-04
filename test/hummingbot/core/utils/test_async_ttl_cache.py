import time
import unittest

from hummingbot.core.utils import async_ttl_cache


class AsyncTTLCacheUnitTest(unittest.IsolatedAsyncioTestCase):

    @async_ttl_cache(ttl=3, maxsize=1)
    async def get_timestamp(self):
        return time.time()

    async def test_async_ttl_cache(self):
        ret_1 = await self.get_timestamp()
        ret_2 = await self.get_timestamp()
        self.assertEqual(ret_1, ret_2)
        time.sleep(2)
        ret_3 = await self.get_timestamp()
        self.assertEqual(ret_2, ret_3)
        time.sleep(2)
        ret_4 = await self.get_timestamp()
        self.assertGreater(ret_4, ret_3)
