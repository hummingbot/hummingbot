"""
Utilities for Deluthium DEX connector.

Contains configuration map, fee schema, and helper functions.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import ConfigDict, Field, SecretStr, field_validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

import hummingbot.connector.exchange.deluthium.deluthium_constants as CONSTANTS


# Fee schema for Deluthium
# Note: Deluthium charges fees in basis points (bps) on each trade
# Typical fee is ~0.1% (10 bps), but can vary based on pair
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0.001"),  # 0.1% = 10 bps
    buy_percent_fee_deducted_from_returns=True
)

# Deluthium is a DEX (decentralized exchange)
CENTRALIZED = False

# Example trading pair
EXAMPLE_PAIR = "WBNB-USDT"

# Broker ID for tracking
BROKER_ID = "HBOT"


def validate_chain_id(value: int) -> int:
    """
    Validate that the chain ID is supported.
    
    :param value: Chain ID to validate
    :return: Validated chain ID
    :raises ValueError: If chain ID is not supported
    """
    supported = list(CONSTANTS.CHAIN_IDS.values())
    if value not in supported:
        raise ValueError(
            f"Invalid chain ID '{value}'. Supported chain IDs: "
            f"56 (BSC), 8453 (Base), 1 (Ethereum)"
        )
    return value


def to_wei(amount: Decimal, decimals: int) -> str:
    """
    Convert a decimal amount to wei units (integer string).
    
    Deluthium API expects all amounts in wei format as decimal strings.
    
    :param amount: Amount in human-readable format
    :param decimals: Token decimals (e.g., 18 for ETH/BNB)
    :return: Amount in wei as string
    """
    wei_amount = int(amount * Decimal(10 ** decimals))
    return str(wei_amount)


def from_wei(wei_amount: str, decimals: int) -> Decimal:
    """
    Convert wei units (integer string) to decimal amount.
    
    :param wei_amount: Amount in wei as string
    :param decimals: Token decimals (e.g., 18 for ETH/BNB)
    :return: Amount in human-readable decimal format
    """
    return Decimal(wei_amount) / Decimal(10 ** decimals)


def convert_symbol_to_hummingbot(pair_symbol: str) -> str:
    """
    Convert Deluthium pair symbol to Hummingbot format.
    
    Deluthium uses hyphen (e.g., "WBNB-USDT")
    Hummingbot uses slash (e.g., "WBNB/USDT")
    
    :param pair_symbol: Deluthium pair symbol
    :return: Hummingbot trading pair format
    """
    return pair_symbol.replace("-", "/")


def convert_symbol_to_deluthium(trading_pair: str) -> str:
    """
    Convert Hummingbot trading pair to Deluthium format.
    
    :param trading_pair: Hummingbot trading pair (e.g., "WBNB/USDT")
    :return: Deluthium pair symbol (e.g., "WBNB-USDT")
    """
    return trading_pair.replace("/", "-")


def is_exchange_information_valid(pair_info: Dict[str, Any]) -> bool:
    """
    Verify if a trading pair is valid and enabled.
    
    :param pair_info: Pair information from the exchange
    :return: True if the pair is valid and enabled
    """
    is_enabled = pair_info.get("is_enabled", True)
    return is_enabled


def get_wrapped_token(chain_id: int) -> Optional[str]:
    """
    Get the wrapped native token address for a chain.
    
    :param chain_id: Chain ID
    :return: Wrapped token address or None if not supported
    """
    return CONSTANTS.WRAPPED_TOKENS.get(chain_id)


def is_native_token(token_address: str) -> bool:
    """
    Check if the token address represents the native token (zero address).
    
    :param token_address: Token address to check
    :return: True if it's the native token
    """
    return token_address.lower() == CONSTANTS.NATIVE_TOKEN_ADDRESS.lower()


class DeluthiumConfigMap(BaseConnectorConfigMap):
    """
    Configuration map for Deluthium connector.
    
    Required credentials:
    - deluthium_api_key: JWT token from Deluthium team (required for all API calls)
    
    Optional settings:
    - deluthium_chain_id: Default chain ID for trading
    - deluthium_wallet_address: Wallet address for RFQ quotes
    """
    
    connector: str = "deluthium"
    
    deluthium_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Deluthium JWT token",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    deluthium_chain_id: int = Field(
        default=56,
        json_schema_extra={
            "prompt": "Enter chain ID (56=BSC, 8453=Base, 1=Ethereum)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    deluthium_wallet_address: str = Field(
        default="",
        json_schema_extra={
            "prompt": "Enter your wallet address for RFQ quotes (optional)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": False,
        }
    )
    
    model_config = ConfigDict(title="deluthium")
    
    @field_validator("deluthium_chain_id", mode="before")
    @classmethod
    def validate_chain(cls, value: int) -> int:
        """Validate chain ID."""
        return validate_chain_id(int(value))


# Keys instance for connector registration
KEYS = DeluthiumConfigMap.model_construct()

# No other domains/testnets currently
OTHER_DOMAINS = []
OTHER_DOMAINS_PARAMETER = {}
OTHER_DOMAINS_EXAMPLE_PAIR = {}
OTHER_DOMAINS_DEFAULT_FEES = {}
OTHER_DOMAINS_KEYS = {}
