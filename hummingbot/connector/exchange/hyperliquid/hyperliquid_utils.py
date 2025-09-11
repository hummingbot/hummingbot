from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict, Field, SecretStr, field_validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Maker rebates(-0.02%) are paid out continuously on each trade directly to the trading wallet.(https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0.00025"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = False

EXAMPLE_PAIR = "HYPE-USD"

BROKER_ID = "HBOT"


def validate_bool(value: str) -> Optional[str]:
    """
    Permissively interpret a string as a boolean
    """
    valid_values = ('true', 'yes', 'y', 'false', 'no', 'n')
    if value.lower() not in valid_values:
        return f"Invalid value, please choose value from {valid_values}"


class HyperliquidConfigMap(BaseConnectorConfigMap):
    connector: str = "hyperliquid"
    hyperliquid_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Arbitrum wallet private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    use_vault: bool = Field(
        default="no",
        json_schema_extra={
            "prompt": "Do you want to use the vault address?(Yes/No)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    hyperliquid_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Arbitrum or vault address",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )

    @field_validator("use_vault", mode="before")
    @classmethod
    def validate_bool(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            ret = validate_bool(v)
            if ret is not None:
                raise ValueError(ret)
        return v


KEYS = HyperliquidConfigMap.model_construct()

OTHER_DOMAINS = ["hyperliquid_testnet"]
OTHER_DOMAINS_PARAMETER = {"hyperliquid_testnet": "hyperliquid_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"hyperliquid_testnet": "HYPE-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"hyperliquid_testnet": [0, 0.025]}


class HyperliquidTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "hyperliquid_testnet"
    hyperliquid_testnet_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Arbitrum wallet private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    use_vault: bool = Field(
        default="no",
        json_schema_extra={
            "prompt": "Do you want to use the vault address?(Yes/No)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    hyperliquid_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Arbitrum or vault address",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="hyperliquid")

    @field_validator("use_vault", mode="before")
    @classmethod
    def validate_bool(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            ret = validate_bool(v)
            if ret is not None:
                raise ValueError(ret)
        return v


OTHER_DOMAINS_KEYS = {"hyperliquid_testnet": HyperliquidTestnetConfigMap.model_construct()}
