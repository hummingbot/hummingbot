from decimal import Decimal
from typing import Dict, Union

from pydantic import ConfigDict, Field, field_validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.connector.exchange.injective_v2.injective_v2_utils import (
    ACCOUNT_MODES,
    FEE_CALCULATOR_MODES,
    NETWORK_MODES,
    InjectiveMainnetNetworkMode,
    InjectiveMessageBasedTransactionFeeCalculatorMode,
    InjectiveReadOnlyAccountMode,
)
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = False
EXAMPLE_PAIR = "INJ-USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
)


class InjectiveConfigMap(BaseConnectorConfigMap):
    # Setting a default dummy configuration to allow the bot to create a dummy instance to fetch all trading pairs
    connector: str = "injective_v2_perpetual"
    receive_connector_configuration: bool = Field(default=True)
    network: Union[tuple(NETWORK_MODES.values())] = Field(
        default=InjectiveMainnetNetworkMode(),
        json_schema_extra={
            "prompt": lambda cm: f"Select the network ({'/'.join(list(NETWORK_MODES.keys()))})",
            "prompt_on_new": True,
        }
    )
    account_type: Union[tuple(ACCOUNT_MODES.values())] = Field(
        default=InjectiveReadOnlyAccountMode(),
        json_schema_extra={
            "prompt": lambda cm: f"Select the type of account ({'/'.join(list(ACCOUNT_MODES.keys()))})",
            "prompt_on_new": True
        },
    )
    fee_calculator: Union[tuple(FEE_CALCULATOR_MODES.values())] = Field(
        default=InjectiveMessageBasedTransactionFeeCalculatorMode(),
        discriminator="name",
        json_schema_extra={
            "prompt": lambda cm: f"Select the fee calculator ({'/'.join(list(FEE_CALCULATOR_MODES.keys()))})",
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="injective_v2_perpetual")

    @field_validator("network", mode="before")
    @classmethod
    def validate_network(cls, v: Union[(str, Dict) + tuple(NETWORK_MODES.values())]):
        if isinstance(v, tuple(NETWORK_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in NETWORK_MODES:
            raise ValueError(
                f"Invalid network, please choose a value from {list(NETWORK_MODES.keys())}."
            )
        else:
            sub_model = NETWORK_MODES[v].model_construct()
        return sub_model

    @field_validator("account_type", mode="before")
    @classmethod
    def validate_account_type(cls, v: Union[(str, Dict) + tuple(ACCOUNT_MODES.values())]):
        if isinstance(v, tuple(ACCOUNT_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in ACCOUNT_MODES:
            raise ValueError(
                f"Invalid account type, please choose a value from {list(ACCOUNT_MODES.keys())}."
            )
        else:
            sub_model = ACCOUNT_MODES[v].model_construct()
        return sub_model

    @field_validator("fee_calculator", mode="before")
    @classmethod
    def validate_fee_calculator(cls, v: Union[(str, Dict) + tuple(FEE_CALCULATOR_MODES.values())]):
        if isinstance(v, tuple(FEE_CALCULATOR_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in FEE_CALCULATOR_MODES:
            raise ValueError(
                f"Invalid fee calculator, please choose a value from {list(FEE_CALCULATOR_MODES.keys())}."
            )
        else:
            sub_model = FEE_CALCULATOR_MODES[v].model_construct()
        return sub_model

    def create_data_source(self):
        return self.account_type.create_data_source(
            network=self.network.network(),
            rate_limits=self.network.rate_limits(),
            fee_calculator_mode=self.fee_calculator,
        )


KEYS = InjectiveConfigMap.model_construct()
