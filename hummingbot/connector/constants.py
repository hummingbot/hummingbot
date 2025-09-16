"""
Constants for Hummingbot connectors.
Minimal implementation to support connector development.
"""

# Default intervals
DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_HEARTBEAT_INTERVAL = 30.0

# Order types
class OrderType:
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    LIMIT_MAKER = "LIMIT_MAKER"

# Trade types
class TradeType:
    BUY = "BUY"
    SELL = "SELL"

# Order states
class OrderState:
    PENDING_CREATE = "PENDING_CREATE"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    PENDING_CANCEL = "PENDING_CANCEL"
    CANCELED = "CANCELED"
    FAILED = "FAILED"

# WebSocket constants
WS_HEARTBEAT_TIME_INTERVAL = 30.0

# Decimal constants
from decimal import Decimal
s_decimal_NaN = Decimal("NaN")
s_decimal_0 = Decimal("0")
s_decimal_1 = Decimal("1")
