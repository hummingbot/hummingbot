from decimal import Decimal
from typing import Optional

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Maker rebates(-0.02%) are paid out continuously on each trade directly to the trading wallet.(https://derive.gitbook.io/derive-docs/trading/fees)
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0.00025"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = False

EXAMPLE_PAIR = "BTC-USD"

BROKER_ID = "HBOT"


def validate_bool(value: str) -> Optional[str]:
    """
    Permissively interpret a string as a boolean
    """
    valid_values = ('true', 'yes', 'y', 'false', 'no', 'n')
    if value.lower() not in valid_values:
        return f"Invalid value, please choose value from {valid_values}"


class DeriveConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="derive", client_data=None)
    derive_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your wallet private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    sub_id: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Subaccount ID",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    derive_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Walllet or Subaccount address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )


KEYS = DeriveConfigMap.construct()

OTHER_DOMAINS = ["derive_testnet"]
OTHER_DOMAINS_PARAMETER = {"derive_testnet": "derive_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"derive_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"derive_testnet": [0, 0.025]}


class DeriveTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="derive_testnet", client_data=None)
    derive_testnet_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your wallet private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    sub_id: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Subaccount Id",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    derive_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Walllet or subaccount address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "derive"


OTHER_DOMAINS_KEYS = {"derive_testnet": DeriveTestnetConfigMap.construct()}
