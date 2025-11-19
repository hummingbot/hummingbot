from decimal import Decimal
from typing import Literal, Optional

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


def validate_wallet_mode(value: str) -> Optional[str]:
    """
    Check if the value is a valid mode
    """
    allowed = ('arb_wallet', 'api_wallet')

    if isinstance(value, str):
        formatted_value = value.strip().lower()

        if formatted_value in allowed:
            return formatted_value

    raise ValueError(f"Invalid wallet mode '{value}', choose from: {allowed}")


def validate_bool(value: str) -> Optional[str]:
    """
    Permissively interpret a string as a boolean
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        formatted_value = value.strip().lower()
        truthy = {"yes", "y", "true", "1"}
        falsy = {"no", "n", "false", "0"}

        if formatted_value in truthy:
            return True
        if formatted_value in falsy:
            return False

    raise ValueError(f"Invalid value, please choose value from {truthy.union(falsy)}")


class HyperliquidConfigMap(BaseConnectorConfigMap):
    connector: str = "hyperliquid"
    hyperliquid_mode: Literal["arb_wallet", "api_wallet"] = Field(
        default="arb_wallet",
        json_schema_extra={
            "prompt": "Select connection mode (arb_wallet/api_wallet)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    use_vault: bool = Field(
        default="no",
        json_schema_extra={
            "prompt": "Do you want to use the Vault address? (Yes/No)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    hyperliquid_address: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: (
                "Enter your Vault address"
                if getattr(cm, "use_vault", False)
                else "Enter your Arbitrum wallet address"
            ),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    hyperliquid_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: {
                "arb_wallet": "Enter your Arbitrum wallet private key",
                "api_wallet": "Enter your API wallet private key (from https://app.hyperliquid.xyz/API)"
            }.get(getattr(cm, "hyperliquid_mode", "arb_wallet")),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="hyperliquid")

    @field_validator("hyperliquid_mode", mode="before")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        """Used for client-friendly error output."""
        return validate_wallet_mode(value)

    @field_validator("use_vault", mode="before")
    @classmethod
    def validate_use_vault(cls, value: str):
        """Used for client-friendly error output."""
        return validate_bool(value)

    @field_validator("hyperliquid_address", mode="before")
    @classmethod
    def validate_address(cls, value: str):
        """Used for client-friendly error output."""
        if isinstance(value, str):
            if value.startswith("HL:"):
                # Strip out the "HL:" that the HyperLiquid Vault page adds to vault addresses
                return value[3:]
        return value


KEYS = HyperliquidConfigMap.model_construct()

OTHER_DOMAINS = ["hyperliquid_testnet"]
OTHER_DOMAINS_PARAMETER = {"hyperliquid_testnet": "hyperliquid_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"hyperliquid_testnet": "HYPE-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"hyperliquid_testnet": [0, 0.025]}


class HyperliquidTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "hyperliquid_testnet"
    hyperliquid_testnet_mode: Literal["arb_wallet", "api_wallet"] = Field(
        default="arb_wallet",
        json_schema_extra={
            "prompt": "Select connection mode (arb_wallet/api_wallet)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    use_vault: bool = Field(
        default="no",
        json_schema_extra={
            "prompt": "Do you want to use the Vault address? (Yes/No)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    hyperliquid_testnet_address: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: (
                "Enter your Vault address"
                if getattr(cm, "use_vault", False)
                else "Enter your Arbitrum wallet address"
            ),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    hyperliquid_testnet_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: {
                "arb_wallet": "Enter your Arbitrum wallet private key",
                "api_wallet": "Enter your API wallet private key (from https://app.hyperliquid.xyz/API)"
            }.get(getattr(cm, "hyperliquid_mode", "arb_wallet")),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="hyperliquid")

    @field_validator("hyperliquid_testnet_mode", mode="before")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        """Used for client-friendly error output."""
        return validate_wallet_mode(value)

    @field_validator("use_vault", mode="before")
    @classmethod
    def validate_use_vault(cls, value: str):
        """Used for client-friendly error output."""
        return validate_bool(value)

    @field_validator("hyperliquid_testnet_address", mode="before")
    @classmethod
    def validate_address(cls, value: str):
        """Used for client-friendly error output."""
        if isinstance(value, str):
            if value.startswith("HL:"):
                # Strip out the "HL:" that the HyperLiquid Vault page adds to vault addresses
                return value[3:]
        return value


OTHER_DOMAINS_KEYS = {
    "hyperliquid_testnet": HyperliquidTestnetConfigMap.model_construct()
}
