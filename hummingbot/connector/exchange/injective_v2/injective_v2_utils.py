from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = False
EXAMPLE_PAIR = "INJ-USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
)


class InjectiveConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="injective_v2", const=True, client_data=None)
    injective_private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Injective trading account private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    injective_subaccount_index: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Injective trading account subaccount index",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    injective_granter_address: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter the Injective address of the granter account (portfolio account)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    injective_granter_subaccount_index: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter the Injective granter subaccount index (portfolio subaccount index)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "injective"


KEYS = InjectiveConfigMap.construct()

OTHER_DOMAINS = ["injective_v2_testnet"]
OTHER_DOMAINS_PARAMETER = {"injective_v2_testnet": "testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"injective_v2_testnet": EXAMPLE_PAIR}
OTHER_DOMAINS_DEFAULT_FEES = {"injective_v2_testnet": DEFAULT_FEES}


class InjectiveTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="injective_v2_testnet", const=True, client_data=None)
    injective_private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Injective trading account private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    injective_subaccount_index: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Injective trading account subaccount index",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    injective_granter_address: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter the Injective address of the granter account (portfolio account)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    injective_granter_subaccount_index: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter the Injective granter subaccount index (portfolio subaccount index)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "injective_v2_testnet"


OTHER_DOMAINS_KEYS = {"injective_v2_testnet": InjectiveTestnetConfigMap.construct()}
