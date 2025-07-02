"""
Backward compatibility module for common types.
These are kept to avoid breaking existing code that imports from this module.
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Match, Optional, Pattern


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


# Token symbol unwrapping utilities
# W{TOKEN} only applies to a few special tokens. It should NOT match all W-prefixed token names like WAVE or WOW.
CAPITAL_W_SYMBOLS_PATTERN = re.compile(r"^W(BTC|ETH|AVAX|ALBT|XRP|POL)")
SMALL_W_SYMBOLS_PATTERN = re.compile(r"^w([A-Z0-9]+)")
DOT_E_SYMBOLS_PATTERN = re.compile(r"^([A-Z0-9]+)\.e$")


def unwrap_token_symbol(on_chain_token_symbol: str) -> str:
    """
    Unwrap wrapped token symbols (e.g., WETH -> ETH, WBTC -> BTC).

    :param on_chain_token_symbol: Token symbol from chain
    :return: Unwrapped token symbol
    """
    patterns: List[Pattern] = [
        CAPITAL_W_SYMBOLS_PATTERN,
        SMALL_W_SYMBOLS_PATTERN,
        DOT_E_SYMBOLS_PATTERN
    ]
    for p in patterns:
        m: Optional[Match] = p.search(on_chain_token_symbol)
        if m is not None:
            return m.group(1)
    return on_chain_token_symbol


# Re-export for backward compatibility
__all__ = [
    "PlaceOrderResult",
    "CancelOrderResult",
    "unwrap_token_symbol",
]
