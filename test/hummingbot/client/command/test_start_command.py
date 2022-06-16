import asyncio
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from test.mock.mock_cli import CLIMockingAssistant
from types import ModuleType
from typing import Awaitable
from unittest.mock import MagicMock, call, patch

from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.model.sql_connection_manager import SQLConnectionManager
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class StartCommandTest(unittest.TestCase):
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher")
    def setUp(self, _: MagicMock) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

        self.async_run_with_timeout(read_system_configs_from_yml())

        self.app = HummingbotApplication()
        self.app.strategy_file_name = "dca_example"

        self.cli_mock_assistant = CLIMockingAssistant(self.app.app)
        self.cli_mock_assistant.start()
        self.global_config_backup = deepcopy(global_config_map)
        self.mock_strategy_name = "test-strategy"

    def tearDown(self) -> None:
        self.cli_mock_assistant.stop()
        self.reset_global_config()
        db_path = Path(SQLConnectionManager.create_db_path(db_name=self.mock_strategy_name))
        db_path.unlink(missing_ok=True)
        super().tearDown()

    def reset_global_config(self):
        for key, value in self.global_config_backup.items():
            global_config_map[key] = value

    @staticmethod
    def get_async_sleep_fn(delay: float):
        async def async_sleep(*_, **__):
            await asyncio.sleep(delay)

        return async_sleep

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def async_run_with_timeout_coroutine_must_raise_timeout(self, coroutine: Awaitable, timeout: float = 1):
        class DesiredError(Exception):
            pass

        async def run_coro_that_raises(coro: Awaitable):
            try:
                await coro
            except asyncio.TimeoutError:
                raise DesiredError

        try:
            self.async_run_with_timeout(run_coro_that_raises(coroutine), timeout)
        except DesiredError:  # the coroutine raised an asyncio.TimeoutError as expected
            raise asyncio.TimeoutError
        except asyncio.TimeoutError:  # the coroutine did not finish on time
            raise RuntimeError

    # Test a call with a standard Lite Strategy script initializing markets in the class
    def test_start_script_strategy_default(self):
        if 'scripts.dca_example' in sys.modules:
            del sys.modules['scripts.dca_example']

        class_wo_initialize: ModuleType = ScriptStrategyBase.load_script_class("dca_example")

        with patch.object(ScriptStrategyBase, 'load_script_class') as load_script_class:
            load_script_class.return_value = class_wo_initialize
            with patch.object(HummingbotApplication, '_initialize_markets') as initialize_markets:
                self.app.start_script_strategy()

        self.assertEqual(load_script_class.call_args_list, [call(self.app.strategy_file_name)])
        self.assertEqual(initialize_markets.call_args_list, [call([('binance_paper_trade', ['BTC-USDT'])])])
        self.assertEqual(self.app.strategy.markets, {'binance_paper_trade': {'BTC-USDT'}})

    # Test a call with a Lite Strategy script providing the initialize_from_yml method (overriding the base method)
    def test_start_script_strategy_config(self):
        if 'scripts.dca_example' in sys.modules:
            del sys.modules['scripts.dca_example']

        class_w_initialize: ModuleType = ScriptStrategyBase.load_script_class("dca_example")

        with patch.object(ScriptStrategyBase, 'initialize_from_yml', create=True) as initialize_from_yml:
            initialize_from_yml.return_value = {'kucoin': {'ALGO-ETH', 'ALGO-USDT', 'AVAX-USDT', 'AVAX-BTC'}}
            with patch.object(ScriptStrategyBase, 'load_script_class') as load_script_class:
                load_script_class.return_value = class_w_initialize
                with patch.object(HummingbotApplication, '_initialize_markets'):
                    self.app.start_script_strategy()

        self.assertEqual(load_script_class.call_args_list, [call(self.app.strategy_file_name)])
        self.assertEqual(self.app.strategy.markets, {'kucoin': {'ALGO-ETH', 'ALGO-USDT', 'AVAX-USDT', 'AVAX-BTC'}})
