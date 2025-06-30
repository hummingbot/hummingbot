import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Match, Optional, Pattern


class ConnectorType(Enum):
    SWAP = "SWAP"
    CLMM = "CLMM"
    AMM = "AMM"


def get_connector_type(connector_name: str) -> ConnectorType:
    """Determine connector type based on connector name and Gateway's trading type structure.

    Gateway 2.8 has explicit trading types:
    - Jupiter: swap only
    - Meteora: clmm only
    - Raydium: amm and clmm only (no swap)
    - Uniswap: swap, amm, and clmm
    """
    # Extract base connector name without trading type suffix
    base_name = connector_name.split("/")[0].lower()

    # Check for explicit trading type in connector name
    if "/clmm" in connector_name:
        return ConnectorType.CLMM
    elif "/amm" in connector_name:
        return ConnectorType.AMM

    # Handle connectors with only one trading type
    if base_name == "jupiter":
        return ConnectorType.SWAP
    elif base_name == "meteora":
        return ConnectorType.CLMM

    # Default to SWAP for backward compatibility
    return ConnectorType.SWAP


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

# w{TOKEN} generally means a wrapped token on the Ethereum network. e.g. wNXM, wDGLD.
SMALL_W_SYMBOLS_PATTERN = re.compile(r"^w(\w+)")

# {TOKEN}.e generally means a wrapped token on the Avalanche network.
DOT_E_SYMBOLS_PATTERN = re.compile(r"(\w+)\.e$", re.IGNORECASE)

USD_EQUIVALANT_TOKENS = ["USC"]


def unwrap_token_symbol(on_chain_token_symbol: str) -> str:
    patterns: List[Pattern] = [
        CAPITAL_W_SYMBOLS_PATTERN,
        SMALL_W_SYMBOLS_PATTERN,
        DOT_E_SYMBOLS_PATTERN
    ]
    for p in patterns:
        m: Optional[Match] = p.search(on_chain_token_symbol)
        if m is not None:
            return m.group(1)

    if on_chain_token_symbol in USD_EQUIVALANT_TOKENS:
        on_chain_token_symbol = "USDT"
    return on_chain_token_symbol
