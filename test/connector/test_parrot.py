from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../")))
import unittest
import asyncio
from hummingbot.connector.parrot import get_active_campaigns, get_campaign_summary


class ParrotConnectorUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()

    def test_get_active_campaigns(self):
        self.ev_loop.run_until_complete(self._test_get_active_campaigns())

    async def _test_get_active_campaigns(self):
        results = await get_active_campaigns("binance")
        self.assertGreater(len(results), 0)
        for result in results.values():
            print(result)

    def test_get_campaign_summary(self):
        self.ev_loop.run_until_complete(self._test_get_campaign_summary())

    async def _test_get_campaign_summary(self):
        results = await get_campaign_summary("binance", ["RLC-BTC", "RLC-ETH"])
        self.assertLessEqual(len(results), 2)
        for result in results.values():
            print(result)
