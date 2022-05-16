import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Awaitable

from hummingbot.client.config.config_data_types import BaseStrategyConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter, get_strategy_config_map, save_to_yml
from hummingbot.strategy.avellaneda_market_making.avellaneda_market_making_config_map_pydantic import (
    AvellanedaMarketMakingConfigMap,
)


class ConfigHelpersTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def get_async_sleep_fn(delay: float):
        async def async_sleep(*_, **__):
            await asyncio.sleep(delay)
        return async_sleep

    def test_get_strategy_config_map(self):
        cm = get_strategy_config_map(strategy="avellaneda_market_making")
        self.assertIsInstance(cm.hb_config, AvellanedaMarketMakingConfigMap)
        self.assertFalse(hasattr(cm, "market"))  # uninitialized instance

    def test_save_to_yml(self):
        class DummyStrategy(BaseStrategyConfigMap):
            class Config:
                title = "pure_market_making"

            strategy: str = "pure_market_making"

        cm = ClientConfigAdapter(DummyStrategy())
        expected_str = """\
#####################################
###   pure_market_making config   ###
#####################################

strategy: pure_market_making
"""
        with TemporaryDirectory() as d:
            d = Path(d)
            temp_file_name = d / "cm.yml"
            save_to_yml(str(temp_file_name), cm)
            with open(temp_file_name) as f:
                actual_str = f.read()
        self.assertEqual(expected_str, actual_str)
