from decimal import Decimal
from typing import Literal, Optional

from pydantic import ConfigDict, Field, SecretStr, field_validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# EVEDEX fee structure - competitive fees for perpetual trading
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),  # 0.02% maker fee
    taker_percent_fee_decimal=Decimal("0.0005"),  # 0.05% taker fee
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

BROKER_ID = "HBOT"


def validate_auth_mode(value: str) -> Optional[str]:
    """
    Validate the authentication mode.
    
    Args:
        value: The auth mode value
        
    Returns:
        Validated auth mode
        
    Raises:
        ValueError: If invalid mode
    """
    allowed = ('wallet', 'api_key')

    if isinstance(value, str):
        formatted_value = value.strip().lower()
        if formatted_value in allowed:
            return formatted_value

    raise ValueError(f"Invalid auth mode '{value}', choose from: {allowed}")


def validate_bool(value: str) -> Optional[bool]:
    """
    Permissively interpret a string as a boolean.
    
    Args:
        value: String to interpret as boolean
        
    Returns:
        Boolean value
        
    Raises:
        ValueError: If value cannot be interpreted as boolean
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

    raise ValueError(f"Invalid value, please choose value from truthy or falsy values")


class EvedexPerpetualConfigMap(BaseConnectorConfigMap):
    """Configuration map for EVEDEX Perpetual connector."""
    
    connector: str = "evedex_perpetual"
    
    evedex_perpetual_auth_mode: Literal["wallet", "api_key"] = Field(
        default="wallet",
        json_schema_extra={
            "prompt": "Select authentication mode (wallet/api_key)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    evedex_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: (
                "Enter your API key"
                if getattr(cm, "evedex_perpetual_auth_mode", "wallet") == "api_key"
                else "Enter your wallet address"
            ),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    evedex_perpetual_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: (
                "Enter your API secret"
                if getattr(cm, "evedex_perpetual_auth_mode", "wallet") == "api_key"
                else "Enter your wallet private key"
            ),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    model_config = ConfigDict(title="evedex_perpetual")

    @field_validator("evedex_perpetual_auth_mode", mode="before")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        """Validate authentication mode."""
        return validate_auth_mode(value)


KEYS = EvedexPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["evedex_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"evedex_perpetual_testnet": "evedex_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"evedex_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"evedex_perpetual_testnet": [0.02, 0.05]}


class EvedexPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    """Configuration map for EVEDEX Perpetual Testnet connector."""
    
    connector: str = "evedex_perpetual_testnet"
    
    evedex_perpetual_testnet_auth_mode: Literal["wallet", "api_key"] = Field(
        default="wallet",
        json_schema_extra={
            "prompt": "Select authentication mode (wallet/api_key)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    evedex_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: (
                "Enter your API key"
                if getattr(cm, "evedex_perpetual_testnet_auth_mode", "wallet") == "api_key"
                else "Enter your wallet address"
            ),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    evedex_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: (
                "Enter your API secret"
                if getattr(cm, "evedex_perpetual_testnet_auth_mode", "wallet") == "api_key"
                else "Enter your wallet private key"
            ),
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    model_config = ConfigDict(title="evedex_perpetual_testnet")

    @field_validator("evedex_perpetual_testnet_auth_mode", mode="before")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        """Validate authentication mode."""
        return validate_auth_mode(value)


OTHER_DOMAINS_KEYS = {
    "evedex_perpetual_testnet": EvedexPerpetualTestnetConfigMap.model_construct()
}
