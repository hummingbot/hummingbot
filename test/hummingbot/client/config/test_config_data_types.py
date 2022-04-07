import asyncio
import json
import unittest
from datetime import date, datetime, time
from decimal import Decimal
from typing import Awaitable, Dict
from unittest.mock import patch

from pydantic import Field
from pydantic.fields import FieldInfo

from hummingbot.client.config.config_data_types import (
    BaseClientModel,
    BaseStrategyConfigMap,
    BaseTradingStrategyConfigMap,
    ClientConfigEnum,
    ClientFieldData,
)
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter, ConfigTraversalItem, ConfigValidationError
)


class BaseClientModelTest(unittest.TestCase):
    def test_schema_encoding_removes_client_data_functions(self):
        class DummyModel(BaseClientModel):
            some_attr: str = Field(
                default=...,
                client_data=ClientFieldData(
                    prompt=lambda mi: "Some prompt?",
                    prompt_on_new=True,
                ),
            )

        schema = DummyModel.schema_json()
        j = json.loads(schema)
        expected = {
            "is_secure": False,
            "prompt": None,
            "prompt_on_new": True,
        }
        self.assertEqual(expected, j["properties"]["some_attr"]["client_data"])

    def test_traverse(self):
        class DoubleNestedModel(BaseClientModel):
            double_nested_attr: float = Field(default=3.0)

            class Config:
                title = "double_nested_model"

        class NestedModel(BaseClientModel):
            nested_attr: str = Field(default="some value")
            double_nested_model: DoubleNestedModel = Field(default=DoubleNestedModel())

            class Config:
                title = "nested_model"

        class DummyModel(BaseClientModel):
            some_attr: int = Field(default=1, client_data=ClientFieldData())
            nested_model: NestedModel = Field(default=NestedModel())
            another_attr: Decimal = Field(default=Decimal("1.0"))

            class Config:
                title = "dummy_model"

        expected = [
            ConfigTraversalItem(0, "some_attr", "some_attr", 1, "1", ClientFieldData(), None),
            ConfigTraversalItem(
                0, "nested_model", "nested_model", ClientConfigAdapter(NestedModel()), "nested_model", None, None
            ),
            ConfigTraversalItem(1, "nested_model.nested_attr", "nested_attr", "some value", "some value", None, None),
            ConfigTraversalItem(
                1,
                "nested_model.double_nested_model",
                "double_nested_model",
                ClientConfigAdapter(DoubleNestedModel()),
                "double_nested_model",
                None,
                None,
            ),
            ConfigTraversalItem(
                2, "nested_model.double_nested_model.double_nested_attr", "double_nested_attr", 3.0, "3.0", None, None
            ),
        ]
        cm = ClientConfigAdapter(DummyModel())

        for expected, actual in zip(expected, cm.traverse()):
            self.assertEqual(expected.depth, actual.depth)
            self.assertEqual(expected.config_path, actual.config_path)
            self.assertEqual(expected.attr, actual.attr)
            self.assertEqual(expected.value, actual.value)
            self.assertEqual(expected.printable_value, actual.printable_value)
            self.assertEqual(expected.client_field_data, actual.client_field_data)
            self.assertIsInstance(actual.field_info, FieldInfo)

    def test_generate_yml_output_dict_with_comments(self):
        class SomeEnum(ClientConfigEnum):
            ONE = "one"

        class DoubleNestedModel(BaseClientModel):
            double_nested_attr: datetime = Field(
                default=datetime(2022, 1, 1, 10, 30),
                description="Double nested attr description"
            )

        class NestedModel(BaseClientModel):
            nested_attr: str = Field(
                default="some value",
                description="Nested attr\nmultiline description",
            )
            double_nested_model: DoubleNestedModel = Field(
                default=DoubleNestedModel(),
            )

        class DummyModel(BaseClientModel):
            some_attr: SomeEnum = Field(
                default=SomeEnum.ONE,
                description="Some description",
            )
            nested_model: NestedModel = Field(
                default=NestedModel(),
                description="Nested model description",
            )
            another_attr: Decimal = Field(
                default=Decimal("1.0"),
                description="Some other\nmultiline description",
            )
            non_nested_no_description: time = Field(default=time(10, 30),)
            date_attr: date = Field(default=date(2022, 1, 2))

            class Config:
                title = "dummy_model"

        instance = ClientConfigAdapter(DummyModel())
        res_str = instance.generate_yml_output_str_with_comments()

        expected_str = """\
##############################
###   dummy_model config   ###
##############################

# Some description
some_attr: one

# Nested model description
nested_model:
  # Nested attr
  # multiline description
  nested_attr: some value
  double_nested_model:
    # Double nested attr description
    double_nested_attr: 2022-01-01 10:30:00

# Some other
# multiline description
another_attr: 1.0

non_nested_no_description: '10:30:00'

date_attr: 2022-01-02
"""

        self.assertEqual(expected_str, res_str)


class BaseStrategyConfigMapTest(unittest.TestCase):
    def test_generate_yml_output_dict_title(self):
        class DummyStrategy(BaseStrategyConfigMap):
            class Config:
                title = "pure_market_making"

            strategy: str = "pure_market_making"

        instance = ClientConfigAdapter(DummyStrategy())
        res_str = instance.generate_yml_output_str_with_comments()

        expected_str = """\
#####################################
###   pure_market_making config   ###
#####################################

strategy: pure_market_making
"""

        self.assertEqual(expected_str, res_str)


class BaseTradingStrategyConfigMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.exchange = "binance"
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        config_settings = self.get_default_map()
        self.config_map = ClientConfigAdapter(BaseTradingStrategyConfigMap(**config_settings))

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_default_map(self) -> Dict[str, str]:
        config_settings = {
            "strategy": "pure_market_making",
            "exchange": self.exchange,
            "market": self.trading_pair,
        }
        return config_settings

    @patch(
        "hummingbot.client.config.config_data_types.validate_market_trading_pair"
    )
    def test_validators(self, validate_market_trading_pair_mock):
        with self.assertRaises(ConfigValidationError) as e:
            self.config_map.exchange = "test-exchange"

        error_msg = "Invalid exchange, please choose value from "
        self.assertTrue(str(e.exception).startswith(error_msg))

        alt_pair = "ETH-USDT"
        error_msg = "Failed"
        validate_market_trading_pair_mock.side_effect = (
            lambda m, v: None if v in [self.trading_pair, alt_pair] else error_msg
        )

        self.config_map.market = alt_pair
        self.assertEqual(alt_pair, self.config_map.market)

        with self.assertRaises(ConfigValidationError) as e:
            self.config_map.market = "XXX-USDT"

        self.assertTrue(str(e.exception).startswith(error_msg))
