from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS


# GRVT time-in-force values
TIF_GOOD_TILL_TIME = 1
TIF_ALL_OR_NONE = 2
TIF_IMMEDIATE_OR_CANCEL = 3
TIF_FILL_OR_KILL = 4


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    """
    Convert Hummingbot trading pair format (BTC-USDT) to GRVT format (BTC_USDT_Perp).
    GRVT perpetual instruments follow the pattern: {BASE}_{QUOTE}_Perp
    """
    base, quote = hb_trading_pair.split("-")
    return f"{base}_{quote}_Perp"


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    """
    Convert GRVT instrument name (BTC_USDT_Perp) to Hummingbot format (BTC-USDT).
    """
    parts = exchange_trading_pair.split("_")
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return exchange_trading_pair


def get_order_type_and_tif(order_type: OrderType) -> Tuple[bool, int]:
    """
    Returns (is_market, time_in_force) for a given Hummingbot OrderType.
    """
    if order_type == OrderType.MARKET:
        return True, TIF_IMMEDIATE_OR_CANCEL
    elif order_type == OrderType.LIMIT:
        return False, TIF_GOOD_TILL_TIME
    elif order_type == OrderType.LIMIT_MAKER:
        return False, TIF_GOOD_TILL_TIME
    return False, TIF_GOOD_TILL_TIME


def is_buy(trade_type: TradeType, position_action: PositionAction) -> bool:
    """
    Determine if this is a buy (long open or short close).
    """
    if trade_type == TradeType.BUY:
        return True
    return False


def get_new_client_order_id(
    is_buy: bool,
    trading_pair: str,
    hbot_order_id_prefix: str = "",
    max_id_len: Optional[int] = None,
) -> str:
    """Generate a client order ID."""
    import random
    import string
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    side = "B" if is_buy else "S"
    pair = trading_pair.replace("-", "")[:6]
    client_id = f"{hbot_order_id_prefix}{side}{pair}{suffix}"
    if max_id_len is not None:
        client_id = client_id[:max_id_len]
    return client_id


def parse_trading_rule_from_instrument(instrument: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract trading rule fields from a GRVT instrument definition.
    Returns a dict with keys expected by TradingRule.
    """
    # GRVT instrument fields (based on SDK types)
    base = instrument.get("base", "")
    quote = instrument.get("quote", "")
    trading_pair = f"{base}-{quote}" if base and quote else convert_from_exchange_trading_pair(
        instrument.get("instrument", "")
    )

    min_order_size = Decimal(str(instrument.get("minSize", "0.001")))
    max_order_size = Decimal(str(instrument.get("maxSize", "1000000")))
    tick_size = Decimal(str(instrument.get("tickSize", "0.1")))
    step_size = Decimal(str(instrument.get("stepSize", "0.001")))
    min_notional = Decimal(str(instrument.get("minNotional", "1")))

    return {
        "trading_pair": trading_pair,
        "min_order_size": min_order_size,
        "max_order_size": max_order_size,
        "min_price_increment": tick_size,
        "min_base_amount_increment": step_size,
        "min_notional_size": min_notional,
        "buy_order_collateral_token": quote,
        "sell_order_collateral_token": quote,
    }


def parse_order_status(raw_status: str) -> str:
    """Normalize GRVT order status to Hummingbot OrderState key."""
    return raw_status.upper()


def format_price(price: Decimal) -> str:
    return f"{price:.8f}".rstrip("0").rstrip(".")


def format_size(size: Decimal) -> str:
    return f"{size:.8f}".rstrip("0").rstrip(".")
