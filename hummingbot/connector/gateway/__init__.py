"""
Gateway connector package for Hummingbot.

This package provides a unified interface for connecting to blockchain DEXs
through the Gateway service. It supports multiple trading types (swap, AMM, CLMM)
and multiple chains (Ethereum, Solana).
"""

# Core components
from .core import GatewayConnector, GatewayHttpClient

# Order tracking
from .gateway_in_flight_order import GatewayInFlightOrder
from .gateway_order_tracker import GatewayOrderTracker

# Models
from .models import (
    ConnectorConfig,
    PoolInfo,
    Position,
    PriceQuote,
    TokenInfo,
    TradingType,
    TransactionResult,
    TransactionStatus,
)

# Trading type handlers
from .trading_types import AMMHandler, CLMMHandler, SwapHandler

# Utilities
from .utils import (
    GatewayConnectorFactory,
    calculate_price_from_amounts,
    estimate_transaction_fee,
    format_trading_pair,
    get_connector_base_name,
    get_connector_trading_type,
    is_connector_compatible,
    parse_connector_trading_pair,
    validate_wallet_address,
)

__all__ = [
    # Core
    "GatewayHttpClient",
    "GatewayConnector",
    # Order tracking
    "GatewayInFlightOrder",
    "GatewayOrderTracker",
    # Models
    "ConnectorConfig",
    "PoolInfo",
    "Position",
    "PriceQuote",
    "TokenInfo",
    "TradingType",
    "TransactionResult",
    "TransactionStatus",
    # Trading handlers
    "AMMHandler",
    "CLMMHandler",
    "SwapHandler",
    # Utils
    "GatewayConnectorFactory",
    "calculate_price_from_amounts",
    "estimate_transaction_fee",
    "format_trading_pair",
    "get_connector_base_name",
    "get_connector_trading_type",
    "is_connector_compatible",
    "parse_connector_trading_pair",
    "validate_wallet_address",
]

# Version
__version__ = "2.0.0"
