import json
import unittest
from decimal import Decimal

from pydantic import Field

from hummingbot.client.config.config_data_types import (
    BaseClientModel, ClientFieldData, ClientConfigEnum, BaseStrategyConfigMap
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

    def test_generate_yml_output_dict_with_comments(self):
        class SomeEnum(ClientConfigEnum):
            ONE = "one"

        class DoubleNestedModel(BaseClientModel):
            double_nested_attr: float = Field(
                default=3.0,
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
            non_nested_no_description: int = Field(
                default=2,
            )

            class Config:
                title = "dummy_model"

        instance = DummyModel()
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
    double_nested_attr: 3.0

# Some other
# multiline description
another_attr: 1.0

non_nested_no_description: 2
"""

        self.assertEqual(expected_str, res_str)


class BaseStrategyConfigMapTest(unittest.TestCase):
    def test_generate_yml_output_dict_title(self):
        instance = BaseStrategyConfigMap(strategy="pure_market_making")
        res_str = instance.generate_yml_output_str_with_comments()

        expected_str = """\
##############################################
###   Pure Market Making Strategy config   ###
##############################################

strategy: pure_market_making
"""

        self.assertEqual(expected_str, res_str)
