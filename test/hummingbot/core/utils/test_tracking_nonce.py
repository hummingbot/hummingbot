from unittest import TestCase
import asyncio
import hummingbot.core.utils.tracking_nonce as tracking_nonce


class TrackingNonceTest(TestCase):

    def test_get_tracking_nonce(self):
        nonce = tracking_nonce.get_tracking_nonce()
        self.assertIsNotNone(nonce)
        new_nonce = tracking_nonce.get_tracking_nonce()
        self.assertGreater(new_nonce, nonce)

    def test_get_low_res_tracking_nonce(self):
        nonce = tracking_nonce.get_tracking_nonce_low_res()
        self.assertIsNotNone(nonce)
        new_nonce = tracking_nonce.get_tracking_nonce_low_res()
        self.assertGreater(new_nonce, nonce)

    def test_get_concurrent_nonce_in_low_res(self):
        async def task():
            return tracking_nonce.get_tracking_nonce_low_res()
        tasks = [task(), task()]
        ret = asyncio.get_event_loop().run_until_complete(asyncio.gather(*tasks))
        self.assertGreaterEqual(ret[1], ret[0])

    def test_get_concurrent_nonce_in_high_res(self):
        async def task():
            return tracking_nonce.get_tracking_nonce()
        tasks = [task(), task()]
        ret = asyncio.get_event_loop().run_until_complete(asyncio.gather(*tasks))
        self.assertGreaterEqual(ret[1], ret[0])

    def test_resolution_difference_between_high_and_low_res(self):
        async def task():
            return tracking_nonce.get_tracking_nonce()
        tasks = [task(), task()]
        ret = asyncio.get_event_loop().run_until_complete(asyncio.gather(*tasks))
        high_res_diff = ret[1] - ret[0]

        async def task():
            return tracking_nonce.get_tracking_nonce_low_res()
        tasks = [task(), task()]
        ret = asyncio.get_event_loop().run_until_complete(asyncio.gather(*tasks))
        low_res_diff = ret[1] - ret[0]

        self.assertGreater(high_res_diff, low_res_diff)
