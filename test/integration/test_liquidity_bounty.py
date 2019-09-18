#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import asyncio
import time
import unittest
import contextlib
import logging
import random
import string

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.client.liquidity_bounty.bounty_utils import LiquidityBounty
from hummingbot.client.liquidity_bounty.liquidity_bounty_config_map import liquidity_bounty_config_map
from hummingbot.client.config.config_helpers import read_configs_from_yml
from hummingbot.core.utils.wallet_setup import list_wallets
from hummingbot.core.utils.async_utils import (
    asyncio_ensure_future,
    asyncio_gather,
)


logging.basicConfig(level=logging.DEBUG)


class LiquidityBountyUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read_configs_from_yml()
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.bounty: LiquidityBounty = LiquidityBounty.get_instance()
        cls.bounty.start()

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = asyncio_ensure_future(asyncio_gather(*tasks))
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

    def test_register(self):
        random_email: str = "".join(random.choice(string.ascii_lowercase[:12]) for i in range(7)) + "@hummingbot.io"
        random_eth_address: str = list_wallets()[0]

        try:
            [results] = self.run_parallel(self.bounty.register(email=random_email, eth_address=random_eth_address))
            self.assertEqual(results["participation_status"], "valid")
        except Exception as e:
            self.assertTrue("email/ethereum_address is already registered" in str(e))

    def test_fetch_client_status(self):
        self.assertTrue(liquidity_bounty_config_map["liquidity_bounty_client_id"].value is not None)
        self.run_parallel(self.bounty.fetch_client_status())
        self.assertEqual(self.bounty.status()["participation_status"], "valid")

    def test_fetch_last_timestamp(self):
        self.assertTrue(liquidity_bounty_config_map["liquidity_bounty_client_id"].value is not None)
        self.run_parallel(self.bounty.fetch_last_timestamp())
        self.assertGreater(self.bounty._last_submitted_trade_timestamp, -1)

    def test_submit_trades(self):
        self.assertTrue(liquidity_bounty_config_map["liquidity_bounty_client_id"].value is not None)
        self.run_parallel(self.bounty.submit_trades())


if __name__ == "__main__":
    unittest.main()
