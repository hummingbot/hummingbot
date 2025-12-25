import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal

from .evedex_perpetual_constants import DAY_ZERO


def generate_order_id_v2(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    days = (now - DAY_ZERO).days
    
    if days < 0:
        raise ValueError(f"Cannot generate order ID for date before {DAY_ZERO}")
    
    hex_part = uuid.uuid4().hex[:26]
    return f"{days:05d}:{hex_part}"


def normalize_price_qty(
    price: float,
    qty: float,
    price_scale: int,
    qty_scale: int
) -> Tuple[int, int]:
    if price < 0:
        raise ValueError("Price must be non-negative")
    if qty <= 0:
        raise ValueError("Quantity must be positive")
    
    price_decimal = Decimal(str(price)) * Decimal(10 ** price_scale)
    qty_decimal = Decimal(str(qty)) * Decimal(10 ** qty_scale)
    
    price_int = int(price_decimal)
    qty_int = int(qty_decimal)
    
    if price_int < 0 or qty_int <= 0:
        raise ValueError(
            f"Normalized values must be positive: "
            f"price={price_int}, qty={qty_int}"
        )
    
    return price_int, qty_int


def denormalize_price_qty(
    price_int: int,
    qty_int: int,
    price_scale: int,
    qty_scale: int
) -> Tuple[float, float]:
    price = float(price_int) / (10 ** price_scale)
    qty = float(qty_int) / (10 ** qty_scale)
    return price, qty


def to_exchange_symbol(trading_pair: str) -> str:
    """
    Convert Hummingbot trading pair to EVEDEX instrument format.
    """
    return trading_pair.replace("-", "").upper()


def to_trading_pair(exchange_symbol: str) -> str:
    """
    Convert EVEDEX instrument to Hummingbot trading pair format.
    """
    # Try common quote currencies in order of preference
    quote_currencies = ['USDT', 'USD', 'USDC', 'DAI']
    
    exchange_symbol = exchange_symbol.upper()
    
    for quote in quote_currencies:
        if exchange_symbol.endswith(quote):
            base = exchange_symbol[:-len(quote)]
            return f"{base}-{quote}"
    
    if len(exchange_symbol) >= 6:
        return f"{exchange_symbol[:-4]}-{exchange_symbol[-4:]}"
    elif len(exchange_symbol) >= 5:
        return f"{exchange_symbol[:-3]}-{exchange_symbol[-3:]}"
    
    return exchange_symbol


def sign_request(
    secret: str,
    method: str,
    path: str,
    timestamp: int,
    body: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate HMAC-SHA256 signature for API request.
    Example:
        >>> signature = sign_request(
        ...     "secret_key",
        ...     "POST",
        ...     "/api/v2/order/limit",
        ...     1234567890000,
        ...     {"orderId": "00001:abc123", "instrument": "BTCUSD"}
        ... )
    """
    parts = [str(timestamp), method.upper(), path]
    
    if body:
        body_str = json.dumps(body, sort_keys=True, separators=(',', ':'))
        parts.append(body_str)
    
    message = '\n'.join(parts)
    
    signature = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def get_timestamp_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def parse_timestamp(ts: Any) -> Optional[float]:
    if ts is None:
        return None
    
    try:
        if isinstance(ts, (int, float)):
            if ts > 1e10:
                return ts / 1000.0
            return float(ts)
        
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.timestamp()
    except (ValueError, AttributeError):
        pass
    
    return None


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_order_params(
    price: Optional[float],
    quantity: float,
    order_type: str
) -> None:
    if quantity <= 0:
        raise ValueError(f"Quantity must be positive, got {quantity}")
    
    if order_type in ["limit", "limit_maker", "stop_limit"]:
        if price is None:
            raise ValueError(f"Price is required for {order_type} orders")
        if price <= 0:
            raise ValueError(f"Price must be positive, got {price}")


def format_trading_pair(base: str, quote: str) -> str:
    return f"{base.upper()}-{quote.upper()}"


def split_trading_pair(trading_pair: str) -> Tuple[str, str]:
    parts = trading_pair.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid trading pair format: {trading_pair}")
    return parts[0].upper(), parts[1].upper()
