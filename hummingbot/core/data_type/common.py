"""
Common data types for Hummingbot framework.
Minimal implementation to support connector development.
"""

from decimal import Decimal
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass


class OrderType(Enum):
    """Order types."""
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    LIMIT_MAKER = "LIMIT_MAKER"


class TradeType(Enum):
    """Trade types."""
    BUY = 1
    SELL = 2


class OrderState(Enum):
    """Order states."""
    PENDING_CREATE = "PENDING_CREATE"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    PENDING_CANCEL = "PENDING_CANCEL"
    CANCELED = "CANCELED"
    FAILED = "FAILED"


@dataclass
class TradingPair:
    """Trading pair data structure."""
    base_asset: str
    quote_asset: str
    
    def __str__(self) -> str:
        return f"{self.base_asset}-{self.quote_asset}"


@dataclass
class OrderBookEntry:
    """Order book entry data structure."""
    price: Decimal
    amount: Decimal
    update_id: int


@dataclass
class Trade:
    """Trade data structure."""
    trading_pair: str
    trade_type: TradeType
    price: Decimal
    amount: Decimal
    timestamp: float
    trade_id: Optional[str] = None
