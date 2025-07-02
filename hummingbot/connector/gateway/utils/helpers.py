"""
Helper utilities for Gateway connectors.
"""
from decimal import Decimal
from typing import List, Optional, Tuple

from ..models import TradingType


def parse_connector_trading_pair(connector_trading_pair: str) -> Tuple[str, str]:
    """
    Parse a connector trading pair string.

    :param connector_trading_pair: Trading pair like "SOL-USDC"
    :return: Tuple of (base_token, quote_token)
    """
    parts = connector_trading_pair.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid trading pair format: {connector_trading_pair}")
    return parts[0], parts[1]


def is_connector_compatible(
    connector_trading_types: List[TradingType],
    required_type: TradingType
) -> bool:
    """
    Check if a connector supports a required trading type.

    :param connector_trading_types: List of supported trading types
    :param required_type: Required trading type
    :return: True if compatible
    """
    return required_type in connector_trading_types


def calculate_price_from_amounts(
    base_amount: Decimal,
    quote_amount: Decimal,
    is_buy: bool
) -> Decimal:
    """
    Calculate price from base and quote amounts.

    :param base_amount: Base token amount
    :param quote_amount: Quote token amount
    :param is_buy: True for buy orders
    :return: Price
    """
    if base_amount == 0:
        return Decimal("0")

    if is_buy:
        # For buy orders, price = quote spent / base received
        return quote_amount / base_amount
    else:
        # For sell orders, price = quote received / base spent
        return quote_amount / base_amount


def format_trading_pair(base_token: str, quote_token: str) -> str:
    """
    Format tokens into trading pair string.

    :param base_token: Base token symbol
    :param quote_token: Quote token symbol
    :return: Trading pair string
    """
    return f"{base_token}-{quote_token}"


def get_connector_base_name(connector_name: str) -> str:
    """
    Get the base name of a connector (without trading type suffix).

    :param connector_name: Full connector name (e.g., "raydium/amm")
    :return: Base name (e.g., "raydium")
    """
    return connector_name.split("/")[0]


def get_connector_trading_type(connector_name: str) -> Optional[str]:
    """
    Get the trading type suffix from a connector name.

    :param connector_name: Full connector name (e.g., "raydium/amm")
    :return: Trading type suffix (e.g., "amm") or None
    """
    parts = connector_name.split("/")
    return parts[1] if len(parts) > 1 else None


def estimate_transaction_fee(
    chain: str,
    compute_units: int,
    priority_fee_per_cu: int
) -> Decimal:
    """
    Estimate transaction fee based on chain and parameters.

    :param chain: Chain name
    :param compute_units: Compute units used
    :param priority_fee_per_cu: Priority fee per compute unit
    :return: Estimated fee in native currency
    """
    if chain.lower() == "solana":
        # For Solana: fee in SOL = (compute_units * priority_fee_per_cu) / 1e9
        # priority_fee_per_cu is in microlamports
        return Decimal(compute_units * priority_fee_per_cu) / Decimal("1e9")
    elif chain.lower() == "ethereum":
        # For Ethereum: fee in ETH = (gas_used * gas_price) / 1e18
        # priority_fee_per_cu represents gas price in Gwei
        gas_price_wei = priority_fee_per_cu * 1e9
        return Decimal(compute_units * gas_price_wei) / Decimal("1e18")
    else:
        return Decimal("0")


def validate_wallet_address(chain: str, address: str) -> bool:
    """
    Basic validation of wallet address format.

    :param chain: Chain name
    :param address: Wallet address
    :return: True if valid format
    """
    if not address:
        return False

    if chain.lower() == "solana":
        # Solana addresses are base58 encoded, typically 32-44 characters
        return 32 <= len(address) <= 44 and address.isalnum()
    elif chain.lower() == "ethereum":
        # Ethereum addresses start with 0x and have 40 hex characters
        return (
            len(address) == 42 and
            address.startswith("0x") and
            all(c in "0123456789abcdefABCDEF" for c in address[2:])
        )
    else:
        # Unknown chain, just check if not empty
        return True
