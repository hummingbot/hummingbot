import asyncio
import unittest
from os.path import join
from typing import Awaitable
from unittest.mock import mock_open, patch

from hummingbot import root_path
from hummingbot.client.config.config_helpers import load_yml_into_cm
from hummingbot.client.config.config_var import ConfigVar


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

    def test_load_yml_into_cm_key_not_in_template(self):
        fee_overrides_config_template_path: str = join(root_path(), "conf/templates/conf_fee_overrides_TEMPLATE.yml")
        template_content = """
            template_version: 12
            binance_percent_fee_token:  # BNB
        """
        fee_overrides_config_path: str = join(root_path(), "conf/conf_fee_overrides.yml")
        config_content = """
            template_version: 12
            kucoin_percent_fee_token: KCS
        """

        fee_overrides_config_map = {
            "binance_percent_fee_token": ConfigVar(key="binance_percent_fee_token", prompt="test prompt"),
            "kucoin_percent_fee_token": ConfigVar(key="kucoin_percent_fee_token", prompt="test prompt")}

        m = mock_open(read_data=config_content)
        m.side_effect = (m.return_value, mock_open(read_data=template_content).return_value)

        with patch('hummingbot.client.config.config_helpers.isfile') as m_isfile:
            with patch('builtins.open', m):
                m_isfile.return_value = True
                self.async_run_with_timeout(load_yml_into_cm(fee_overrides_config_path,
                                                             fee_overrides_config_template_path,
                                                             fee_overrides_config_map))

        var = fee_overrides_config_map.get("kucoin_percent_fee_token")
        self.assertEqual(var.value, None)

    def test_load_yml_into_cm_key_in_template(self):
        fee_overrides_config_template_path: str = join(root_path(), "conf/templates/conf_fee_overrides_TEMPLATE.yml")
        template_content = """
            template_version: 12
            binance_percent_fee_token:  # BNB
            kucoin_percent_fee_token:
       """
        fee_overrides_config_path: str = join(root_path(), "conf/conf_fee_overrides.yml")
        config_content = """
            template_version: 12
            kucoin_percent_fee_token: KCS
        """

        fee_overrides_config_map = {
            "binance_percent_fee_token": ConfigVar(key="binance_percent_fee_token", prompt="test prompt"),
            "kucoin_percent_fee_token": ConfigVar(key="kucoin_percent_fee_token", prompt="test prompt")}

        m = mock_open(read_data=config_content)
        m.side_effect = (m.return_value, mock_open(read_data=template_content).return_value)

        with patch('hummingbot.client.config.config_helpers.isfile') as m_isfile:
            with patch('builtins.open', m):
                m_isfile.return_value = True
                self.async_run_with_timeout(load_yml_into_cm(fee_overrides_config_path,
                                                             fee_overrides_config_template_path,
                                                             fee_overrides_config_map))

        var = fee_overrides_config_map.get("kucoin_percent_fee_token")
        self.assertEqual(var.value, "KCS")
