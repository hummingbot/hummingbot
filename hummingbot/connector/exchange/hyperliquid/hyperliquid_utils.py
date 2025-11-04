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


def validate_mode(value: str) -> Optional[str]:
    """
    Check if the value is a valid mode
    """
    allowed = ('wallet', 'vault', 'api_wallet')

    if isinstance(value, str) and value.lower() not in allowed:
        return f"Invalid mode '{value}', choose from: {allowed}"

    return None


class HyperliquidConfigMap(BaseConnectorConfigMap):
    connector: str = "hyperliquid"
    hyperliquid_mode: Literal["wallet", "vault", "api_wallet"] = Field(
        default="wallet",
        json_schema_extra={
            "prompt": "Select connection mode (wallet / vault / api_wallet)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    hyperliquid_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: {
                "wallet": "Enter your Arbitrum address",
                "vault": "Enter vault address",
                "api_wallet": "Enter your main Arbitrum wallet address (NOT the API wallet address)"
            }.get(getattr(cm, "hyperliquid_mode", "wallet")),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    hyperliquid_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: {
                "wallet": "Enter your Arbitrum wallet private key",
                "vault": "Enter your Arbitrum wallet private key",
                "api_wallet": "Enter your API wallet private key"
            }.get(getattr(cm, "hyperliquid_mode", "wallet")),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="hyperliquid")

    @field_validator("hyperliquid_mode", mode="before")
    @classmethod
    def validate_hyperliquid_mode(cls, value: str) -> str:
        """Used for client-friendly error output."""
        returned_error = validate_mode(value)

        if returned_error is not None:
            raise ValueError(returned_error)

        return value.lower()

    @field_validator("hyperliquid_api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            if v.startswith("HL:"):
                # Strip out the "HL:" that the HyperLiquid Vault page adds to vault addresses
                return v[3:]
        return v


KEYS = HyperliquidConfigMap.model_construct()

OTHER_DOMAINS = ["hyperliquid_testnet"]
OTHER_DOMAINS_PARAMETER = {"hyperliquid_testnet": "hyperliquid_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"hyperliquid_testnet": "HYPE-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"hyperliquid_testnet": [0, 0.025]}


class HyperliquidTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "hyperliquid_testnet"
    hyperliquid_testnet_mode: Literal["wallet", "vault", "api_wallet"] = Field(
        default="wallet",
        json_schema_extra={
            "prompt": "Select connection mode (wallet / vault / api_wallet)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    hyperliquid_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: {
                "wallet": "Enter your Arbitrum address",
                "vault": "Enter vault address",
                "api_wallet": "Enter your main Arbitrum wallet address (NOT the API wallet address)"
            }.get(getattr(cm, "hyperliquid_testnet_mode", "wallet")),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    hyperliquid_testnet_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: {
                "wallet": "Enter your Arbitrum wallet private key",
                "vault": "Enter your Arbitrum wallet private key",
                "api_wallet": "Enter your API wallet private key"
            }.get(getattr(cm, "hyperliquid_testnet_mode", "wallet")),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="hyperliquid")

    @field_validator("hyperliquid_testnet_mode", mode="before")
    @classmethod
    def validate_hyperliquid_mode(cls, value: str) -> str:
        """Used for client-friendly error output."""
        returned_error = validate_mode(value)

        if returned_error is not None:
            raise ValueError(returned_error)

        return value.lower()

    @field_validator("hyperliquid_testnet_api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            if v.startswith("HL:"):
                # Strip out the "HL:" that the HyperLiquid Vault page adds to vault addresses
                return v[3:]
        return v


OTHER_DOMAINS_KEYS = {
    "hyperliquid_testnet": HyperliquidTestnetConfigMap.model_construct()
}
