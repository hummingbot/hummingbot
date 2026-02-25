"""Backpack utility functions."""
from typing import Optional

from hummingbot.core.data_type.common import OrderType, TradeType


def get_backpack_trading_pair(hummingbot_trading_pair: str) -> str:
    """
    Converts a Hummingbot trading pair to Backpack symbol format.
    
    Hummingbot: SOL-USDC
    Backpack: SOL_USDC
    
    :param hummingbot_trading_pair: Trading pair in Hummingbot format
    :return: Trading pair in Backpack format
    """
    return hummingbot_trading_pair.replace("-", "_")


def get_hummingbot_trading_pair(backpack_symbol: str) -> Optional[str]:
    """
    Converts a Backpack symbol to Hummingbot trading pair format.
    
    Backpack: SOL_USDC
    Hummingbot: SOL-USDC
    
    :param backpack_symbol: Symbol in Backpack format
    :return: Trading pair in Hummingbot format
    """
    if not backpack_symbol:
        return None
    return backpack_symbol.replace("_", "-")


def convert_order_side(trade_type: TradeType) -> str:
    """
    Converts Hummingbot TradeType to Backpack side.
    
    :param trade_type: Hummingbot TradeType
    :return: Backpack side string
    """
    from hummingbot.connector.exchange.backpack.backpack_constants import SIDE_BID, SIDE_ASK
    
    if trade_type == TradeType.BUY:
        return SIDE_BID
    elif trade_type == TradeType.SELL:
        return SIDE_ASK
    else:
        raise ValueError(f"Unknown trade type: {trade_type}")


def convert_order_type(order_type: OrderType) -> str:
    """
    Converts Hummingbot OrderType to Backpack order type.
    
    :param order_type: Hummingbot OrderType
    :return: Backpack order type string
    """
    from hummingbot.connector.exchange.backpack.backpack_constants import (
        ORDER_TYPE_LIMIT,
        ORDER_TYPE_MARKET,
    )
    
    if order_type == OrderType.LIMIT or order_type == OrderType.LIMIT_MAKER:
        return ORDER_TYPE_LIMIT
    elif order_type == OrderType.MARKET:
        return ORDER_TYPE_MARKET
    else:
        raise ValueError(f"Unknown order type: {order_type}")


def convert_time_in_force(time_in_force: str) -> str:
    """
    Converts Hummingbot time in force to Backpack format.
    
    :param time_in_force: Time in force string
    :return: Backpack time in force string
    """
    from hummingbot.connector.exchange.backpack.backpack_constants import (
        TIME_IN_FORCE_GTC,
        TIME_IN_FORCE_IOC,
        TIME_IN_FORCE_FOK,
    )
    
    time_in_force = time_in_force.upper()
    
    if time_in_force == "GTC":
        return TIME_IN_FORCE_GTC
    elif time_in_force == "IOC":
        return TIME_IN_FORCE_IOC
    elif time_in_force == "FOK":
        return TIME_IN_FORCE_FOK
    else:
        return TIME_IN_FORCE_GTC  # Default to GTC


def convert_backpack_order_status(status: str) -> str:
    """
    Converts Backpack order status to Hummingbot format.
    
    :param status: Backpack order status
    :return: Hummingbot order status
    """
    status_mapping = {
        "New": "OPEN",
        "PartiallyFilled": "PARTIALLY_FILLED",
        "Filled": "FILLED",
        "Cancelled": "CANCELED",
        "Expired": "EXPIRED",
        "Rejected": "FAILED",
    }
    return status_mapping.get(status, "UNKNOWN")


def parse_backpack_symbol(symbol: str) -> tuple[str, str]:
    """
    Parses a Backpack symbol into base and quote assets.
    
    :param symbol: Backpack symbol (e.g., "SOL_USDC")
    :return: Tuple of (base_asset, quote_asset)
    """
    parts = symbol.split("_")
    if len(parts) >= 2:
        return parts[0], parts[1]
    raise ValueError(f"Invalid Backpack symbol format: {symbol}")
