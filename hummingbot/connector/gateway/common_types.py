import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Match, Optional, Pattern


class ConnectorType(Enum):
    SWAP = "SWAP"
    CLMM = "CLMM"
    AMM = "AMM"


def get_connector_type(connector_name: str) -> ConnectorType:
    if "/clmm" in connector_name:
        return ConnectorType.CLMM
    elif "/amm" in connector_name:
        return ConnectorType.AMM
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
