#!/usr/bin/env python
import logging
from os.path import join, realpath
import sys;sys.path.insert(0, realpath(join(__file__, "../../../")))

import asyncio
import time
import unittest
import contextlib
import logging

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.client.liquidity_bounty.bounty_utils import LiquidityBounty
from hummingbot.client.config.config_helpers import read_configs_from_yml


logging.basicConfig(level=logging.INFO)


class LiquidityBountyUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read_configs_from_yml()
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.bounty: LiquidityBounty = LiquidityBounty.get_instance()
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        cls.bounty.start()

    @classmethod
    async def wait_til_ready(cls):
        await cls.bounty._wait_till_ready()

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = asyncio.ensure_future(asyncio.gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_fetch_active_bounties(self):
        self.run_parallel(self.bounty.fetch_active_bounties())
        self.assertGreater(len(self.bounty.active_bounties()), 0)


if __name__ == "__main__":
    unittest.main()
