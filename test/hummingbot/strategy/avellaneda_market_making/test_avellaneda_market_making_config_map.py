import unittest
from copy import deepcopy

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.strategy.avellaneda_market_making.avellaneda_market_making_config_map import (
    avellaneda_market_making_config_map,
    maker_trading_pair_prompt,
    order_amount_prompt,
    execution_time_start_prompt,
    execution_time_end_prompt,
    validate_exchange_trading_pair,
    validate_execution_timeframe,
    validate_execution_time,
    on_validated_execution_timeframe
)


class AvellanedaMarketMakingConfigMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(avellaneda_market_making_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            avellaneda_market_making_config_map[key] = value

    def test_order_amount_prompt(self):
        avellaneda_market_making_config_map["market"].value = self.trading_pair
        prompt = order_amount_prompt()
        expected = f"What is the amount of {self.base_asset} per order? >>> "

        self.assertEqual(expected, prompt)

    def test_maker_trading_pair_prompt(self):
        exchange = avellaneda_market_making_config_map["exchange"].value = "binance"
        example = AllConnectorSettings.get_example_pairs().get(exchange)

        prompt = maker_trading_pair_prompt()
        expected = f"Enter the token trading pair you would like to trade on {exchange} (e.g. {example}) >>> "

        self.assertEqual(expected, prompt)

    def test_execution_time_prompts(self):
        avellaneda_market_making_config_map["execution_timeframe"].value = "from_date_to_date"
        prompt = execution_time_start_prompt()
        expected = "Please enter the start date and time (YYYY-MM-DD HH:MM:SS) >>> "
        self.assertEqual(expected, prompt)

        avellaneda_market_making_config_map["execution_timeframe"].value = "daily_between_times"
        prompt = execution_time_start_prompt()
        expected = "Please enter the start time (HH:MM:SS) >>> "
        self.assertEqual(expected, prompt)

        avellaneda_market_making_config_map["execution_timeframe"].value = "from_date_to_date"
        prompt = execution_time_end_prompt()
        expected = "Please enter the end date and time (YYYY-MM-DD HH:MM:SS) >>> "
        self.assertEqual(expected, prompt)

        avellaneda_market_making_config_map["execution_timeframe"].value = "daily_between_times"
        prompt = execution_time_end_prompt()
        expected = "Please enter the end time (HH:MM:SS) >>> "
        self.assertEqual(expected, prompt)

    def test_validators(self):
        avellaneda_market_making_config_map["exchange"].value = "binance"
        value = validate_exchange_trading_pair("ETH-USDT")
        self.assertIsNone(value)

        value = validate_exchange_trading_pair("XXX-USDT")
        self.assertFalse(value)

        value = validate_execution_timeframe("infinite")
        self.assertIsNone(value)

        value = validate_execution_timeframe("from_date_to_date")
        self.assertIsNone(value)

        value = validate_execution_timeframe("daily_between_times")
        self.assertIsNone(value)

        value = validate_execution_timeframe("XXX")
        expected = "Invalid timeframe, please choose value from ['infinite', 'from_date_to_date', 'daily_between_times']"
        self.assertEqual(expected, value)

        avellaneda_market_making_config_map["execution_timeframe"].value = "from_date_to_date"

        value = validate_execution_time("2021-01-01 12:00:00")
        self.assertIsNone(value)

        value = validate_execution_time("2021-01-01 30:00:00")
        expected = "Incorrect date time format (expected is YYYY-MM-DD HH:MM:SS)"
        self.assertEqual(expected, value)

        value = validate_execution_time("12:00:00")
        expected = "Incorrect date time format (expected is YYYY-MM-DD HH:MM:SS)"
        self.assertEqual(expected, value)

        avellaneda_market_making_config_map["execution_timeframe"].value = "daily_between_times"

        value = validate_execution_time("12:00:00")
        self.assertIsNone(value)

        value = validate_execution_time("30:00:00")
        expected = "Incorrect time format (expected is HH:MM:SS)"
        self.assertEqual(expected, value)

        value = validate_execution_time("2021-01-01 12:00:00")
        expected = "Incorrect time format (expected is HH:MM:SS)"
        self.assertEqual(expected, value)

        avellaneda_market_making_config_map["start_time"].value = "12:00:00"
        avellaneda_market_making_config_map["end_time"].value = "13:00:00"

        on_validated_execution_timeframe("")

        value = avellaneda_market_making_config_map["start_time"].value
        self.assertIsNone(value)

        value = avellaneda_market_making_config_map["end_time"].value
        self.assertIsNone(value)
