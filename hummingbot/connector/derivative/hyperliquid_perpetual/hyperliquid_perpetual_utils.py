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
    connector: str = "hyperliquid_perpetual"
    use_vault: bool = Field(
        default="no",
        json_schema_extra={
            "prompt": "Do you want to use the vault address? (Set up at https://app.hyperliquid.xyz/vaults) (Yes/No)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    use_api_wallet: bool = Field(
        default="no",
        json_schema_extra={
            "prompt": "Do you want to use an API wallet? (More secure) (Set up at https://app.hyperliquid.xyz/API) (Yes/No)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    hyperliquid_perpetual_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt_callable": lambda cm: (
                "Enter your API wallet private key" if getattr(cm, "use_api_wallet", False)
                else "Enter your Arbitrum wallet private key"),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    hyperliquid_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt_callable": lambda cm: (
                "Enter vault address" if getattr(cm, "use_vault", False)
                else "Enter your Arbitrum address (Not the API wallet address!)" if getattr(cm, "use_api_wallet", False)
                else "Enter your Arbitrum address"
            ),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )

    @field_validator("use_vault", "use_api_wallet", mode="before")
    @classmethod
    def validate_bool(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            ret = validate_bool(v)
            if ret is not None:
                raise ValueError(ret)
        return v

    @field_validator("hyperliquid_perpetual_api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            if v.startswith("HL:"):
                # Strip out the "HL:" that the HyperLiquid Vault page adds to vault addresses
                return v[3:]
        return v


KEYS = HyperliquidPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["hyperliquid_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"hyperliquid_perpetual_testnet": "hyperliquid_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"hyperliquid_perpetual_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"hyperliquid_perpetual_testnet": [0, 0.025]}


class HyperliquidPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "hyperliquid_perpetual_testnet"
    use_vault: bool = Field(
        default="no",
        json_schema_extra={
            "prompt": "Do you want to use the vault address? (Set up at https://app.hyperliquid.xyz/vaults) (Yes/No)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    use_api_wallet: bool = Field(
        default="no",
        json_schema_extra={
            "prompt": "Do you want to use an API wallet? (More secure) (Set up at https://app.hyperliquid.xyz/API) (Yes/No)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    hyperliquid_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt_callable": lambda cm: (
                "Enter your API wallet private key" if getattr(cm, "use_api_wallet", False)
                else "Enter your Arbitrum wallet private key"),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    hyperliquid_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt_callable": lambda cm: (
                "Enter vault address" if getattr(cm, "use_vault", False)
                else "Enter your Arbitrum address (Not the API wallet address!)" if getattr(cm, "use_api_wallet", False)
                else "Enter your Arbitrum address"
            ),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="hyperliquid_perpetual")

    @field_validator("use_vault", "use_api_wallet", mode="before")
    @classmethod
    def validate_bool(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            ret = validate_bool(v)
            if ret is not None:
                raise ValueError(ret)
        return v

    @field_validator("hyperliquid_perpetual_testnet_api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            if v.startswith("HL:"):
                # Strip out the "HL:" that the HyperLiquid Vault page adds to vault addresses
                return v[3:]
        return v
        """Used for client-friendly error output."""
        if isinstance(v, str):
            ret = validate_bool(v)
            if ret is not None:
                raise ValueError(ret)
        return v


OTHER_DOMAINS_KEYS = {"hyperliquid_perpetual_testnet": HyperliquidPerpetualTestnetConfigMap.model_construct()}
