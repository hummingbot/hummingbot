import asyncio
import unittest
from copy import deepcopy
from decimal import Decimal
from test.mock.mock_cli import CLIMockingAssistant
from typing import Awaitable, Dict, Optional
from unittest.mock import MagicMock, patch

from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase


class DummyRateSource(RateSourceBase):
    def __init__(self, price_dict: Dict[str, Decimal]):
        self._price_dict = price_dict

    @property
    def name(self):
        return "dummy_rate_source"

    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        return deepcopy(self._price_dict)


class RateCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target_token = "COINALPHA"
        cls.global_token = "HBOT"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)
        cls.original_source = RateOracle.get_instance().source

    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher")
    def setUp(self, _: MagicMock) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

        self.async_run_with_timeout(read_system_configs_from_yml())

        self.app = HummingbotApplication()
        self.cli_mock_assistant = CLIMockingAssistant(self.app.app)
        self.cli_mock_assistant.start()

    def tearDown(self) -> None:
        self.cli_mock_assistant.stop()
        RateOracle.get_instance().source = self.original_source
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_show_token_value(self):
        self.app.client_config_map.global_token.global_token_name = self.global_token
        global_token_symbol = "$"
        self.app.client_config_map.global_token.global_token_symbol = global_token_symbol
        expected_rate = Decimal("2.0")
        dummy_source = DummyRateSource(price_dict={self.trading_pair: expected_rate})
        RateOracle.get_instance().source = dummy_source
        RateOracle.get_instance().quote_token = self.global_token

        self.async_run_with_timeout(self.app.show_token_value(self.target_token))

        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(msg=f"Source: {dummy_source.name}")
        )
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg=f"1 {self.target_token} = {global_token_symbol} {expected_rate} {self.global_token}"
            )
        )

    def test_show_token_value_rate_not_available(self):
        self.app.client_config_map.global_token.global_token_name = self.global_token
        global_token_symbol = "$"
        self.app.client_config_map.global_token.global_token_symbol = global_token_symbol
        expected_rate = Decimal("2.0")
        dummy_source = DummyRateSource(price_dict={self.trading_pair: expected_rate})
        RateOracle.get_instance().source = dummy_source

        self.async_run_with_timeout(self.app.show_token_value("SOMETOKEN"))

        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(msg=f"Source: {dummy_source.name}")
        )
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(msg="Rate is not available.")
        )
