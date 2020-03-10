#!/usr/bin/env python
from os.path import (
    join,
    realpath,
)
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))
import sys; sys.path.append(realpath(join(__file__, "../../bin")))
import unittest
from hummingbot.client.hummingbot_application import HummingbotApplication
from bin.hummingbot import main as hb_main
import asyncio
import time
import inspect
import os
from hummingbot.client import settings
from hummingbot.strategy.pure_market_making.pure_market_making_config_map import pure_market_making_config_map
from hummingbot.client.config.global_config_map import global_config_map
from test.integration.assets.mock_data.fixture_configs import FixtureConfigs
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.client.config.in_memory_config_map import default_strategy_conf_path_prompt


async def wait_til(condition_func, timeout=10):
    start_time = time.perf_counter()
    while True:
        if condition_func():
            return
        elif time.perf_counter() - start_time > timeout:
            raise Exception(f"{inspect.getsource(condition_func).strip()} condition is never met. Time out reached.")
        else:
            await asyncio.sleep(0.1)


async def wait_til_notified(text):
    await wait_til(lambda: text in HummingbotApplication.main_application().app.output_field.document.lines[:-1])


def user_response(text):
    hb = HummingbotApplication.main_application()
    hb.app.set_text(text)
    hb.app.accept(None)
    hb.app.set_text("")


def add_files_extension(folder, file_extensions, additional_extension):
    for f in os.listdir(folder):
        f_path = os.path.join(folder, f)
        if os.path.isfile(f_path):
            extension = os.path.splitext(f_path)[1]
            if extension in file_extensions:
                os.rename(f_path, f_path + f"{additional_extension}")


def remove_files_extension(folder, file_extension):
    for f in os.listdir(folder):
        f_path = os.path.join(folder, f)
        if os.path.isfile(f_path):
            extension = os.path.splitext(f_path)[1]
            if extension == file_extension:
                os.rename(f_path, os.path.splitext(f_path)[0])


def remove_files(folder, file_extensions):
    for f in os.listdir(folder):
        f_path = os.path.join(folder, f)
        if os.path.isfile(f_path):
            extension = os.path.splitext(f_path)[1]
            if extension in file_extensions:
                os.remove(f_path)


class ConfigProcessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.new_event_loop()
        cls.ev_loop.run_until_complete(cls.set_up_class())

    @classmethod
    def tearDownClass(cls) -> None:
        user_response("stop")
        cls.ev_loop.run_until_complete(wait_til(lambda: cls.hb.markets_recorder is None))
        remove_files(settings.CONF_FILE_PATH, [".yml", ".json"])
        remove_files_extension(settings.CONF_FILE_PATH, ".temp")

    @classmethod
    async def set_up_class(cls):
        add_files_extension(settings.CONF_FILE_PATH, [".yml", ".json"], ".temp")
        asyncio.ensure_future(hb_main())
        cls.hb = HummingbotApplication.main_application()
        await wait_til(lambda: ExchangeRateConversion.get_instance()._ready_notifier.is_set())
        await wait_til(lambda: 'Enter "config" to create a bot' in cls.hb.app.output_field.document.text)

    async def verify_config_input(self, expected_prompt_text, input_text):
        self.assertEqual(self.hb.app.prompt_text, expected_prompt_text)
        last_output = str(self.hb.app.output_field.document.lines[-1])
        user_response(input_text)
        await wait_til(lambda: str(self.hb.app.output_field.document.lines[-1]) != last_output)
        await asyncio.sleep(0.1)

    async def _test_pure_mm_basic_til_start(self):
        await self.verify_config_input(">>> ", "config")
        for fixture_config in FixtureConfigs.in_mem_new_pass_configs:
            await self.verify_config_input(fixture_config["prompt"], fixture_config["input"])
        await wait_til(lambda: f'A new config file {settings.CONF_PREFIX}pure_market_making{settings.CONF_POSTFIX}_0'
                               f'.yml created.' in self.hb.app.output_field.document.text)
        for name, config in pure_market_making_config_map.items():
            if config.required and config.value is None:
                await self.verify_config_input(config.prompt, FixtureConfigs.pure_mm_basic_response[name])
        for name, config in global_config_map.items():
            if config.required and config.value is None:
                await self.verify_config_input(config.prompt, FixtureConfigs.global_binance_config[name])
        # input for cancel_order_wait_time is blank, check the assigned value is its default value
        self.assertEqual(pure_market_making_config_map["cancel_order_wait_time"].value,
                         pure_market_making_config_map["cancel_order_wait_time"].default)
        await wait_til(lambda: f"Config process complete." in self.hb.app.output_field.document.text)

    def test_pure_mm_basic_til_start(self):
        self.ev_loop.run_until_complete(self._test_pure_mm_basic_til_start())

    async def _test_pure_mm_basic_import_config_file(self):
        await self.verify_config_input(">>> ", "stop")
        await self.verify_config_input(">>> ", "config")
        await self.verify_config_input("Would you like to reconfigure the bot? (Yes/No) >>> ", "yes")
        for fixture_config in FixtureConfigs.in_mem_existing_pass_import_configs:
            await self.verify_config_input(fixture_config["prompt"], fixture_config["input"])
        await self.verify_config_input(default_strategy_conf_path_prompt(), f"{settings.CONF_PREFIX}pure_market_making"
                                                                            f"{settings.CONF_POSTFIX}_0.yml")
        await wait_til(lambda: f"Config process complete." in self.hb.app.output_field.document.text)

    def test_pure_mm_basic_import_config_file(self):
        self.ev_loop.run_until_complete(self._test_pure_mm_basic_import_config_file())


def suite():
    suite = unittest.TestSuite()
    suite.addTest(ConfigProcessTest('test_pure_mm_basic_til_start'))
    suite.addTest(ConfigProcessTest('test_pure_mm_basic_import_config_file'))
    return suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    runner.run(suite())
