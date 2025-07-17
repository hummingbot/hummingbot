"""
Gateway utility functions and helpers.
"""
from decimal import Decimal
from typing import Any, Dict, List

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState


# Note: parse_trading_type_from_connector_name is now available in command_utils.py
# Keeping this for backward compatibility
def parse_trading_type_from_connector_name(connector_name: str) -> str:
    """
    Extract trading type from connector name.

    :param connector_name: Connector name (e.g., "raydium/amm", "uniswap/clmm")
    :return: Trading type (e.g., "amm", "clmm", "swap")
    """
    from .command_utils import GatewayCommandUtils
    _, trading_type = GatewayCommandUtils.parse_connector_trading_type(connector_name)
    return trading_type or "swap"


def get_default_gateway_url() -> str:
    """Get default Gateway URL from environment or use default."""
    import os
    return os.getenv("GATEWAY_URL", "http://localhost:15888")


def get_gateway_paths(client_config_map) -> Any:
    """
    Get Gateway paths from client config.
    This is a compatibility function for the old gateway_paths module.
    """
    from pathlib import Path

    class GatewayPaths:
        def __init__(self):
            # Get base path from client config or use default
            base_path = Path.home() / ".hummingbot-gateway"
            self.local_certs_path = base_path / "certs"
            self.gateway_certs_path = base_path / "gateway-certs"

    return GatewayPaths()


def build_gateway_api_path(connector: str, trading_type: str, method: str) -> str:
    """
    Build Gateway API path for a connector method.

    :param connector: Base connector name (e.g., "raydium", "uniswap")
    :param trading_type: Trading type (e.g., "amm", "clmm", "swap")
    :param method: API method (e.g., "quote-swap", "pool-info")
    :return: Full API path
    """
    if trading_type == "swap":
        # Aggregators use direct path
        return f"connectors/{connector}/{method}"
    else:
        # AMM/CLMM use trading type in path
        return f"connectors/{connector}/{trading_type}/{method}"


def convert_hb_order_type_to_gateway(order_type: OrderType) -> str:
    """Convert Hummingbot order type to Gateway order type."""
    if order_type == OrderType.LIMIT or order_type == OrderType.LIMIT_MAKER:
        return "LIMIT"
    else:
        return "MARKET"


def convert_gateway_order_status(status: int) -> OrderState:
    """
    Convert Gateway transaction status to Hummingbot order state.

    Gateway statuses:
    - 0: Failed
    - 1: Success
    - 2: Pending
    """
    if status == 0:
        return OrderState.FAILED
    elif status == 1:
        return OrderState.FILLED
    else:
        return OrderState.PENDING_CREATE


def parse_gateway_error(error_response: Dict[str, Any]) -> str:
    """Extract error message from Gateway error response."""
    if isinstance(error_response, dict):
        # Try different error formats
        if "message" in error_response:
            return error_response["message"]
        elif "error" in error_response:
            return error_response["error"]
        elif "errorMessage" in error_response:
            return error_response["errorMessage"]
    return str(error_response)


# Note: normalize_token_symbol is now available in command_utils.py
# Keeping this for backward compatibility
def normalize_token_symbol(symbol: str) -> str:
    """
    Normalize token symbol for consistency.

    :param symbol: Token symbol
    :return: Normalized symbol (uppercase)
    """
    from .command_utils import GatewayCommandUtils
    return GatewayCommandUtils.normalize_token_symbol(symbol)


# Note: This function is also available in helpers.py
def calculate_price_from_amounts(
    base_amount: Decimal,
    quote_amount: Decimal,
    side: TradeType
) -> Decimal:
    """
    Calculate price from base and quote amounts.

    :param base_amount: Base token amount
    :param quote_amount: Quote token amount
    :param side: Trade side (BUY/SELL)
    :return: Calculated price
    """
    # Import from helpers to avoid duplication
    from .helpers import calculate_price_from_amounts as calc_price
    return calc_price(base_amount, quote_amount, side)


def validate_connector_trading_pair(
    connector_name: str,
    trading_pair: str,
    available_pairs: List[str]
) -> bool:
    """
    Validate if a trading pair is supported by a connector.

    :param connector_name: Connector name
    :param trading_pair: Trading pair to validate
    :param available_pairs: List of available trading pairs
    :return: True if valid, False otherwise
    """
    return trading_pair in available_pairs


# Note: format_gateway_exception is now available in command_utils.py
# Keeping this for backward compatibility
def format_gateway_exception(exception: Exception) -> str:
    """
    Format Gateway-related exceptions for user display.

    :param exception: Exception to format
    :return: Formatted error message
    """
    from .command_utils import GatewayCommandUtils
    return GatewayCommandUtils.format_gateway_exception(exception)
