"""
Utility functions for Coins.xyz Exchange Connector

This module contains helper functions and utilities for the Coins.xyz connector,
including data validation, formatting, and conversion functions.
"""

from decimal import Decimal
from typing import Any, Dict, Tuple

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.client.config.config_helpers import BaseConnectorConfigMap
from pydantic import Field, SecretStr
from pydantic.config import ConfigDict


def is_pair_information_valid(pair_info: Dict[str, Any]) -> bool:
    """
    Validate trading pair information from Coins.ph exchange info.
    
    :param pair_info: Trading pair information dictionary
    :return: True if the pair is valid and tradeable, False otherwise
    """
    required_fields = ["symbol", "baseAsset", "quoteAsset", "status"]
    
    # Check if all required fields are present
    if not all(field in pair_info for field in required_fields):
        return False
    
    # Check if the pair is active for trading
    if pair_info.get("status") != "TRADING":
        return False
    
    # Check if spot trading is allowed
    if not pair_info.get("isSpotTradingAllowed", False):
        return False
    
    # Check if the pair has the required permissions
    permissions = pair_info.get("permissions", [])
    if "SPOT" not in permissions:
        return False
    
    return True


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    """
    Convert Hummingbot trading pair format to Coins.ph exchange format.
    
    Example: "BTC-PHP" -> "BTCPHP"
    
    :param hb_trading_pair: Trading pair in Hummingbot format (BASE-QUOTE)
    :return: Trading pair in Coins.ph exchange format
    """
    return hb_trading_pair.replace("-", "")


def convert_from_exchange_trading_pair(exchange_trading_pair: str, 
                                     base_asset: str, 
                                     quote_asset: str) -> str:
    """
    Convert Coins.ph exchange trading pair format to Hummingbot format.
    
    Example: "BTCPHP" with base="BTC", quote="PHP" -> "BTC-PHP"
    
    :param exchange_trading_pair: Trading pair in exchange format
    :param base_asset: Base asset symbol
    :param quote_asset: Quote asset symbol
    :return: Trading pair in Hummingbot format
    """
    return combine_to_hb_trading_pair(base=base_asset, quote=quote_asset)


def parse_exchange_trading_pair(exchange_trading_pair: str) -> str:
    """
    Parse exchange trading pair format to Hummingbot format without requiring base/quote assets.

    :param exchange_trading_pair: Trading pair in exchange format (e.g., "BTCUSDT")
    :return: Trading pair in Hummingbot format (e.g., "BTC-USDT")
    """
    # Common quote assets to try
    quote_assets = ["USDT", "USDC", "BTC", "ETH", "BNB", "BUSD", "DAI", "USD", "EUR", "PHP"]

    exchange_pair = exchange_trading_pair.upper()

    # Try to find a matching quote asset
    for quote in quote_assets:
        if exchange_pair.endswith(quote):
            base = exchange_pair[:-len(quote)]
            if base:  # Make sure base is not empty
                return f"{base}-{quote}"

    # If no match found, try common 3-letter patterns
    if len(exchange_pair) >= 6:
        # Assume last 3-4 characters are quote asset
        for quote_len in [4, 3]:
            if len(exchange_pair) > quote_len:
                base = exchange_pair[:-quote_len]
                quote = exchange_pair[-quote_len:]
                return f"{base}-{quote}"

    # Fallback: return as-is with dash in the middle
    if len(exchange_pair) >= 4:
        mid = len(exchange_pair) // 2
        return f"{exchange_pair[:mid]}-{exchange_pair[mid:]}"

    return exchange_trading_pair


def get_order_type_from_exchange(exchange_order_type: str) -> OrderType:
    """
    Convert Coins.ph order type to Hummingbot OrderType.
    
    :param exchange_order_type: Order type from Coins.ph API
    :return: Corresponding Hummingbot OrderType
    """
    order_type_map = {
        "LIMIT": OrderType.LIMIT,
        "MARKET": OrderType.MARKET,
        "LIMIT_MAKER": OrderType.LIMIT_MAKER,
    }
    
    return order_type_map.get(exchange_order_type.upper(), OrderType.LIMIT)


def get_exchange_order_type(hb_order_type: OrderType) -> str:
    """
    Convert Hummingbot OrderType to Coins.ph order type.
    
    :param hb_order_type: Hummingbot OrderType
    :return: Corresponding Coins.ph order type string
    """
    order_type_map = {
        OrderType.LIMIT: "LIMIT",
        OrderType.MARKET: "MARKET",
        OrderType.LIMIT_MAKER: "LIMIT_MAKER",
    }
    
    return order_type_map.get(hb_order_type, "LIMIT")


def get_trade_type_from_exchange(exchange_side: str) -> TradeType:
    """
    Convert Coins.ph order side to Hummingbot TradeType.
    
    :param exchange_side: Order side from Coins.ph API ("BUY" or "SELL")
    :return: Corresponding Hummingbot TradeType
    """
    return TradeType.BUY if exchange_side.upper() == "BUY" else TradeType.SELL


def get_exchange_trade_type(hb_trade_type: TradeType) -> str:
    """
    Convert Hummingbot TradeType to Coins.ph order side.
    
    :param hb_trade_type: Hummingbot TradeType
    :return: Corresponding Coins.ph order side string
    """
    return "BUY" if hb_trade_type == TradeType.BUY else "SELL"


def format_decimal_for_api(value: Decimal, precision: int = 8) -> str:
    """
    Format a Decimal value for API requests with specified precision.
    
    :param value: Decimal value to format
    :param precision: Number of decimal places
    :return: Formatted string representation
    """
    if value is None or value.is_nan():
        return "0"
    
    # Format with specified precision and remove trailing zeros
    formatted = f"{value:.{precision}f}".rstrip('0').rstrip('.')
    
    # Ensure at least one digit after decimal for very small numbers
    if '.' not in formatted and precision > 0:
        formatted += '.0'
    
    return formatted


def parse_decimal_from_api(value: Any) -> Decimal:
    """
    Parse a decimal value from API response, handling various input types.
    
    :param value: Value from API response (string, int, float, or Decimal)
    :return: Decimal representation of the value
    """
    if value is None:
        return Decimal("0")
    
    if isinstance(value, Decimal):
        return value
    
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return Decimal("0")


def validate_trading_pair_format(trading_pair: str) -> bool:
    """
    Validate that a trading pair is in the correct Hummingbot format.
    
    :param trading_pair: Trading pair string to validate
    :return: True if format is valid, False otherwise
    """
    if not trading_pair or not isinstance(trading_pair, str):
        return False
    
    # Check for hyphen separator
    if "-" not in trading_pair:
        return False
    
    # Split and validate parts
    parts = trading_pair.split("-")
    if len(parts) != 2:
        return False
    
    base, quote = parts
    
    # Check that both parts are non-empty and contain only alphanumeric characters
    if not base or not quote:
        return False
    
    if not base.isalnum() or not quote.isalnum():
        return False
    
    return True


def extract_trading_pair_components(trading_pair: str) -> Tuple[str, str]:
    """
    Extract base and quote assets from a Hummingbot trading pair.
    
    :param trading_pair: Trading pair in format "BASE-QUOTE"
    :return: Tuple of (base_asset, quote_asset)
    :raises ValueError: If trading pair format is invalid
    """
    if not validate_trading_pair_format(trading_pair):
        raise ValueError(f"Invalid trading pair format: {trading_pair}")
    
    base, quote = trading_pair.split("-")
    return base, quote


def build_api_error_message(error_code: int, error_msg: str) -> str:
    """
    Build a standardized error message from Coins.ph API error response.
    
    :param error_code: Error code from API
    :param error_msg: Error message from API
    :return: Formatted error message
    """
    return f"Coins.ph API Error {error_code}: {error_msg}"


def is_temporary_network_error(error_message: str) -> bool:
    """
    Determine if an error is a temporary network issue that should be retried.
    
    :param error_message: Error message to analyze
    :return: True if error appears to be temporary, False otherwise
    """
    temporary_error_indicators = [
        "timeout",
        "connection",
        "network",
        "503",  # Service Unavailable
        "502",  # Bad Gateway
        "504",  # Gateway Timeout
        "429",  # Too Many Requests
    ]
    
    error_lower = error_message.lower()
    return any(indicator in error_lower for indicator in temporary_error_indicators)


# Connector Configuration
CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"
USE_ETHEREUM_WALLET = False
USE_ETH_GAS_LOOKUP = False

# Default trading fees (0.1% maker/taker)
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
    buy_percent_fee_deducted_from_returns=False
)


class CoinsxyzConfigMap(BaseConnectorConfigMap):
    """Configuration map for Coins.xyz exchange connector."""

    connector: str = "coinsxyz"
    coinsxyz_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Coins.xyz API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    coinsxyz_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Coins.xyz secret key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="coinsxyz")


# Export the configuration instance
KEYS = CoinsxyzConfigMap.model_construct()
