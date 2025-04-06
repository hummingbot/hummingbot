from decimal import Decimal
from typing import Optional

from pydantic import Field, SecretStr
from pydantic.class_validators import validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Maker rebates(-0.02%) are paid out continuously on each trade directly to the trading wallet.(https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0.00025"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"

BROKER_ID = "HBOT"


def validate_bool(value: str) -> Optional[str]:
    """
    Permissively interpret a string as a boolean
    """
    valid_values = ('true', 'yes', 'y', 'false', 'no', 'n')
    if value.lower() not in valid_values:
        return f"Invalid value, please choose value from {valid_values}"


class HyperliquidPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="hyperliquid_perpetual", client_data=None)
    hyperliquid_perpetual_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Arbitrum wallet private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    use_vault: bool = Field(
        default="no",
        client_data=ClientFieldData(
            prompt=lambda cm: "Do you want to use the vault address?(Yes/No)",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    hyperliquid_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Arbitrum or vault address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    @validator("use_vault", pre=True)
    def validate_bool(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            ret = validate_bool(v)
            if ret is not None:
                raise ValueError(ret)
        return v


KEYS = HyperliquidPerpetualConfigMap.construct()

OTHER_DOMAINS = ["hyperliquid_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"hyperliquid_perpetual_testnet": "hyperliquid_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"hyperliquid_perpetual_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"hyperliquid_perpetual_testnet": [0, 0.025]}


class HyperliquidPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="hyperliquid_perpetual_testnet", client_data=None)
    hyperliquid_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Arbitrum wallet private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    use_vault: bool = Field(
        default="no",
        client_data=ClientFieldData(
            prompt=lambda cm: "Do you want to use the vault address?(Yes/No)",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    hyperliquid_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Arbitrum or vault address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "hyperliquid_perpetual"

    @validator("use_vault", pre=True)
    def validate_bool(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            ret = validate_bool(v)
            if ret is not None:
                raise ValueError(ret)
        return v


OTHER_DOMAINS_KEYS = {"hyperliquid_perpetual_testnet": HyperliquidPerpetualTestnetConfigMap.construct()}
