"""
Backward compatibility module for common types.
These are kept to avoid breaking existing code that imports from this module.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class PlaceOrderResult:
    update_timestamp: float
    client_order_id: str
    exchange_order_id: Optional[str]
    trading_pair: str
    misc_updates: Dict[str, Any] = field(default_factory=lambda: {})
    exception: Optional[Exception] = None


@dataclass
class CancelOrderResult:
    client_order_id: str
    trading_pair: str
    misc_updates: Dict[str, Any] = field(default_factory=lambda: {})
    not_found: bool = False
    exception: Optional[Exception] = None


def unwrap_token_symbol(on_chain_token_symbol: str) -> str:
    """
    Unwrap wrapped token symbols (e.g., WETH -> ETH, WBTC -> BTC).

    :param on_chain_token_symbol: Token symbol from chain
    :return: Unwrapped token symbol
    """
    # Map of wrapped tokens to their native equivalents
    # Only specific tokens are supported
    wrapped_tokens = {
        "WETH": "ETH",
        "WBTC": "BTC",
        "WAVAX": "AVAX",
        "WBNB": "BNB",
        "WXRP": "XRP",
        "WPOL": "POL",
        "WCELO": "CELO",
    }

    return wrapped_tokens.get(on_chain_token_symbol.upper(), on_chain_token_symbol)


# Re-export for backward compatibility
__all__ = [
    "PlaceOrderResult",
    "CancelOrderResult",
    "unwrap_token_symbol",
]
