#!/usr/bin/env python
from os.path import (
    join,
    realpath,
)
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))
import sys; sys.path.append(realpath(join(__file__, "../../bin")))
from bin.hummingbot import main as hb_main
from hummingbot.client.hummingbot_application import HummingbotApplication
import unittest
import asyncio
import time
import inspect
import os
from hummingbot.client import settings
from hummingbot.client.config.security import Security
from hummingbot.strategy.pure_market_making.pure_market_making_config_map import pure_market_making_config_map
from hummingbot.client.config.global_config_map import global_config_map
from test.debug.fixture_configs import FixtureConfigs


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
        cls.file_no = 0

    @classmethod
    def tearDownClass(cls) -> None:
        remove_files(settings.CONF_FILE_PATH, [".yml", ".json"])
        remove_files_extension(settings.CONF_FILE_PATH, ".temp")
        user_response("stop")
        cls.ev_loop.run_until_complete(wait_til(lambda: cls.hb.markets_recorder is None))

    @classmethod
    async def set_up_class(cls):
        add_files_extension(settings.CONF_FILE_PATH, [".yml", ".json"], ".temp")
        asyncio.ensure_future(hb_main())
        cls.hb = HummingbotApplication.main_application()
        await wait_til(lambda: 'Enter "config" to create a bot' in cls.hb.app.output_field.document.text)

    async def check_prompt_and_input(self, expected_prompt_text, input_text):
        self.assertEqual(self.hb.app.prompt_text, expected_prompt_text)
        last_output = str(self.hb.app.output_field.document.lines[-1])
        user_response(input_text)
        await wait_til(lambda: str(self.hb.app.output_field.document.lines[-1]) != last_output)
        await asyncio.sleep(0.1)

    async def _test_pure_mm_basic_til_start(self):
        config_file_name = f"{settings.CONF_PREFIX}pure_market_making{settings.CONF_POSTFIX}_{self.file_no}.yml"
        await self.check_prompt_and_input(">>> ", "config")
        # For the second time this test is called, it's to reconfigure the bot
        if self.file_no > 0:
            await self.check_prompt_and_input("Would you like to reconfigure the bot? (Yes/No) >>> ", "yes")
        ConfigProcessTest.file_no += 1
        fixture_in_mem = FixtureConfigs.in_mem_new_pass_configs if Security.password is None \
            else FixtureConfigs.in_mem_existing_pass_create_configs
        for fixture_config in fixture_in_mem:
            await self.check_prompt_and_input(fixture_config["prompt"], fixture_config["input"])
        await wait_til(lambda: f'A new config file {config_file_name}' in self.hb.app.output_field.document.text)
        # configs that are required will be prompted
        for config_name, response in FixtureConfigs.pure_mm_basic_responses.items():
            config = pure_market_making_config_map[config_name]
            await self.check_prompt_and_input(config.prompt, response)
        # advance_mode will be asked again as the previous response is not valid.
        await asyncio.sleep(0.2)
        self.assertEqual(self.hb.app.output_field.document.lines[-1],
                         f"{FixtureConfigs.pure_mm_basic_responses['advanced_mode']} "
                         f"is not a valid advanced_mode value")
        await self.check_prompt_and_input(pure_market_making_config_map["advanced_mode"].prompt, "no")

        # input for cancel_order_wait_time is empty, check the assigned value is its default value
        self.assertEqual(pure_market_making_config_map["cancel_order_wait_time"].value,
                         pure_market_making_config_map["cancel_order_wait_time"].default)

        # Check that configs that are not prompted get assigned correct default value
        for name, config in pure_market_making_config_map.items():
            if config.default is not None and name not in FixtureConfigs.pure_mm_basic_responses:
                self.assertEqual(config.value, config.default)

        # if not conf_global_file_exists:
        for name, config in global_config_map.items():
            if config.required and config.value is None:
                await self.check_prompt_and_input(config.prompt, FixtureConfigs.global_binance_config[name])

        self.assertEqual(pure_market_making_config_map["mode"].value,
                         pure_market_making_config_map["mode"].default)
        await wait_til(lambda: "Config process complete." in self.hb.app.output_field.document.text)

    def test_pure_mm_basic_til_start(self):
        self.ev_loop.run_until_complete(self._test_pure_mm_basic_til_start())

    async def _test_pure_mm_basic_import_config_file(self):
        config_file_name = f"{settings.CONF_PREFIX}pure_market_making{settings.CONF_POSTFIX}_0.yml"
        # update the config file to put in some blank and invalid values.
        with open(os.path.join(settings.CONF_FILE_PATH, config_file_name), "r+") as f:
            content = f.read()  # read everything in the file
            f.seek(0)  # rewind
            content = content.replace("bid_place_threshold: 0.01", "bid_place_threshold: ")
            content = content.replace("advanced_mode: false", "advanced_mode: better not")
            f.write(content)  # write the new line before
        await self.check_prompt_and_input(">>> ", "stop")
        await self.check_prompt_and_input(">>> ", "config")
        await self.check_prompt_and_input("Would you like to reconfigure the bot? (Yes/No) >>> ", "yes")
        for fixture_config in FixtureConfigs.in_mem_existing_pass_import_configs:
            await self.check_prompt_and_input(fixture_config["prompt"], fixture_config["input"])
        # await self.check_prompt_and_input(default_strategy_conf_path_prompt(), config_file_name)
        # advanced_mode should be prompted here as its file value not valid.
        await self.check_prompt_and_input(pure_market_making_config_map["bid_place_threshold"].prompt, "0.01")
        await self.check_prompt_and_input(pure_market_making_config_map["advanced_mode"].prompt, "no")
        await wait_til(lambda: "Config process complete." in self.hb.app.output_field.document.text)

    def test_pure_mm_basic_import_config_file(self):
        self.ev_loop.run_until_complete(self._test_pure_mm_basic_import_config_file())

    async def _test_single_configs(self):
        await self.check_prompt_and_input(">>> ", "config bid_place_threshold")
        # try inputting invalid value
        await self.check_prompt_and_input(pure_market_making_config_map["bid_place_threshold"].prompt, "-0.01")
        self.assertEqual(self.hb.app.output_field.document.lines[-1], "-0.01 is not a valid bid_place_threshold value")
        await self.check_prompt_and_input(pure_market_making_config_map["bid_place_threshold"].prompt, "0.01")

    def test_single_configs(self):
        self.ev_loop.run_until_complete(self._test_single_configs())


def suite():
    suite = unittest.TestSuite()
    suite.addTest(ConfigProcessTest('test_pure_mm_basic_til_start'))
    suite.addTest(ConfigProcessTest('test_single_configs'))
    suite.addTest(ConfigProcessTest('test_pure_mm_basic_import_config_file'))
    suite.addTest(ConfigProcessTest('test_pure_mm_basic_til_start'))
    return suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    runner.run(suite())
