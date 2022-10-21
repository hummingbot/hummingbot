import json
import unittest
from datetime import date, datetime, time
from decimal import Decimal
from typing import Union

from pydantic import Field, SecretStr
from pydantic.fields import FieldInfo

from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.config_data_types import BaseClientModel, ClientConfigEnum, ClientFieldData
from hummingbot.client.config.config_helpers import ClientConfigAdapter, ConfigTraversalItem
from hummingbot.client.config.security import Security


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
        client_data=ClientFieldData(),
    )
    nested_model: NestedModel = Field(
        default=NestedModel(),
        description="Nested model description",
    )
    another_attr: Decimal = Field(
        default=Decimal("1.0"),
        description="Some other\nmultiline description",
    )
    non_nested_no_description: time = Field(default=time(10, 30), )
    date_attr: date = Field(default=date(2022, 1, 2))

    class Config:
        title = "dummy_model"


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
            "prompt": None,
            "prompt_on_new": True,
            "is_secure": False,
            "is_connect_key": False,
        }
        self.assertEqual(expected, j["properties"]["some_attr"]["client_data"])

    def test_traverse(self):
        class DoubleNestedModel(BaseClientModel):
            double_nested_attr: float = Field(default=3.0)

            class Config:
                title = "double_nested_model"

        class NestedModelOne(BaseClientModel):
            nested_attr: str = Field(default="some value")
            double_nested_model: DoubleNestedModel = Field(default=DoubleNestedModel())

            class Config:
                title = "nested_mode_one"

        class NestedModelTwo(BaseClientModel):
            class Config:
                title = "nested_mode_two"

        class DummyModel(BaseClientModel):
            some_attr: int = Field(default=1, client_data=ClientFieldData())
            nested_model: Union[NestedModelTwo, NestedModelOne] = Field(default=NestedModelOne())
            another_attr: Decimal = Field(default=Decimal("1.0"))

            class Config:
                title = "dummy_model"

        expected_values = [
            ConfigTraversalItem(0, "some_attr", "some_attr", 1, "1", ClientFieldData(), None, int),
            ConfigTraversalItem(
                0,
                "nested_model",
                "nested_model",
                ClientConfigAdapter(NestedModelOne()),
                "nested_mode_one",
                None,
                None,
                NestedModel,
            ),
            ConfigTraversalItem(
                1, "nested_model.nested_attr", "nested_attr", "some value", "some value", None, None, str
            ),
            ConfigTraversalItem(
                1,
                "nested_model.double_nested_model",
                "double_nested_model",
                ClientConfigAdapter(DoubleNestedModel()),
                "",
                None,
                None,
                DoubleNestedModel,
            ),
            ConfigTraversalItem(
                2,
                "nested_model.double_nested_model.double_nested_attr",
                "double_nested_attr",
                3.0,
                "3.0",
                None,
                None,
                float,
            ),
        ]
        cm = ClientConfigAdapter(DummyModel())

        for expected, actual in zip(expected_values, cm.traverse()):
            self.assertEqual(expected.depth, actual.depth)
            self.assertEqual(expected.config_path, actual.config_path)
            self.assertEqual(expected.attr, actual.attr)
            self.assertEqual(expected.value, actual.value)
            self.assertEqual(expected.printable_value, actual.printable_value)
            self.assertEqual(expected.client_field_data, actual.client_field_data)
            self.assertIsInstance(actual.field_info, FieldInfo)

    def test_generate_yml_output_dict_with_comments(self):
        instance = self._nested_config_adapter()
        res_str = instance.generate_yml_output_str_with_comments()
        expected_str = """\
##############################
###   dummy_model config   ###
##############################

# Some description
some_attr: one

# Nested model description
nested_model:
  nested_attr: some value
  double_nested_model:
    double_nested_attr: 2022-01-01 10:30:00

# Some other
# multiline description
another_attr: 1.0

non_nested_no_description: '10:30:00'

date_attr: 2022-01-02
"""

        self.assertEqual(expected_str, res_str)

    def test_generate_yml_output_dict_with_secret(self):
        class DummyModel(BaseClientModel):
            secret_attr: SecretStr

            class Config:
                title = "dummy_model"

        Security.secrets_manager = ETHKeyFileSecretManger(password="some-password")
        secret_value = "some_secret"
        instance = ClientConfigAdapter(DummyModel(secret_attr=secret_value))
        res_str = instance.generate_yml_output_str_with_comments()
        expected_str = """\
##############################
###   dummy_model config   ###
##############################

secret_attr: """

        self.assertTrue(res_str.startswith(expected_str))
        self.assertNotIn(secret_value, res_str)

    def test_config_paths_includes_all_intermediate_keys(self):
        adapter = self._nested_config_adapter()

        all_config_paths = list(adapter.config_paths())
        expected_config_paths = [
            'some_attr',
            'nested_model',
            'nested_model.nested_attr',
            'nested_model.double_nested_model',
            'nested_model.double_nested_model.double_nested_attr',
            'another_attr',
            'non_nested_no_description',
            'date_attr',
        ]

        self.assertEqual(expected_config_paths, all_config_paths)

    def _nested_config_adapter(self):
        return ClientConfigAdapter(DummyModel())
