from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from pydantic import ConfigDict, Field, SecretStr

import hummingbot.connector.exchange.backpack.backpack_constants as CONSTANTS
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema


# Backpack trading fees (standard tier)
# Maker: 0.02%, Taker: 0.04%
# See: https://docs.backpack.exchange/
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0004"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDC"

BROKER_ID = "HBOT"


class BackpackConfigMap(BaseConnectorConfigMap):
    """Configuration map for Backpack exchange connector."""
    connector: str = "backpack"
    backpack_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Backpack API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    backpack_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Backpack API secret (ED25519 private key)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="backpack")


KEYS = BackpackConfigMap.model_construct()

# No other domains for now
OTHER_DOMAINS = []
OTHER_DOMAINS_PARAMETER = {}
OTHER_DOMAINS_EXAMPLE_PAIR = {}
OTHER_DOMAINS_DEFAULT_FEES = {}
OTHER_DOMAINS_KEYS = {}


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    """
    Convert Hummingbot trading pair format to Backpack format.

    Args:
        hb_trading_pair: Trading pair in Hummingbot format (e.g., "BTC-USDC")

    Returns:
        Trading pair in Backpack format (e.g., "BTC_USDC")
    """
    return hb_trading_pair.replace("-", "_")


def convert_from_exchange_trading_pair(exchange_symbol: str) -> str:
    """
    Convert Backpack symbol to Hummingbot trading pair format.

    Args:
        exchange_symbol: Trading pair in Backpack format (e.g., "BTC_USDC")

    Returns:
        Trading pair in Hummingbot format (e.g., "BTC-USDC")
    """
    # Handle perpetual symbols by removing _PERP suffix for the trading pair
    # but keeping it for proper identification
    return exchange_symbol.replace("_", "-")


def get_base_quote_from_trading_pair(trading_pair: str) -> Tuple[str, str]:
    """
    Extract base and quote assets from a trading pair.

    Args:
        trading_pair: Trading pair in either format

    Returns:
        Tuple of (base_asset, quote_asset)
    """
    # Handle both formats
    if "_" in trading_pair:
        parts = trading_pair.split("_")
    else:
        parts = trading_pair.split("-")

    if len(parts) >= 2:
        return parts[0], parts[1]
    raise ValueError(f"Invalid trading pair format: {trading_pair}")


def is_spot_symbol(symbol: str) -> bool:
    """
    Check if a Backpack symbol is a spot trading pair.

    Args:
        symbol: The exchange symbol (e.g., "BTC_USDC", "BTC_USDC_PERP")

    Returns:
        True if spot, False if derivative
    """
    return not any(suffix in symbol for suffix in ["_PERP", "_IPERP", "_DATED"])


def is_perpetual_symbol(symbol: str) -> bool:
    """
    Check if a Backpack symbol is a perpetual contract.

    Args:
        symbol: The exchange symbol

    Returns:
        True if perpetual
    """
    return "_PERP" in symbol or "_IPERP" in symbol


def parse_order_side(side: str) -> str:
    """
    Convert Backpack order side to standard format.

    Args:
        side: "Bid" or "Ask"

    Returns:
        "BUY" or "SELL"
    """
    return "BUY" if side == CONSTANTS.ORDER_SIDE_BID else "SELL"


def to_exchange_order_side(is_buy: bool) -> str:
    """
    Convert boolean buy flag to Backpack order side.

    Args:
        is_buy: True for buy, False for sell

    Returns:
        "Bid" or "Ask"
    """
    return CONSTANTS.ORDER_SIDE_BID if is_buy else CONSTANTS.ORDER_SIDE_ASK


def parse_order_type(order_type: str) -> str:
    """
    Convert Backpack order type to Hummingbot format.

    Args:
        order_type: "Limit" or "Market"

    Returns:
        "LIMIT" or "MARKET"
    """
    return order_type.upper()


def to_exchange_order_type(order_type: str) -> str:
    """
    Convert Hummingbot order type to Backpack format.

    Args:
        order_type: "LIMIT" or "MARKET"

    Returns:
        "Limit" or "Market"
    """
    return order_type.capitalize()


def decimal_to_str(value: Decimal, precision: int = 8) -> str:
    """
    Convert Decimal to string with specified precision.

    Args:
        value: Decimal value
        precision: Number of decimal places

    Returns:
        String representation
    """
    if value is None:
        return "0"
    return f"{value:.{precision}f}".rstrip("0").rstrip(".")


def parse_balance_response(balance_data: Dict[str, Any]) -> Dict[str, Tuple[Decimal, Decimal]]:
    """
    Parse balance response from Backpack API.

    Args:
        balance_data: Response from /api/v1/capital

    Returns:
        Dict mapping asset name to (available, total) balances
    """
    balances = {}

    # Handle the balances structure from Backpack
    if isinstance(balance_data, dict):
        for asset, data in balance_data.items():
            if isinstance(data, dict):
                available = Decimal(str(data.get("available", "0")))
                locked = Decimal(str(data.get("locked", "0")))
                total = available + locked
                balances[asset] = (available, total)

    return balances


def parse_trading_rule(market_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse market data into trading rule parameters.

    Args:
        market_data: Market info from /api/v1/markets

    Returns:
        Dict with trading rule parameters
    """
    symbol = market_data.get("symbol", "")
    base, quote = get_base_quote_from_trading_pair(symbol)

    return {
        "symbol": symbol,
        "base_asset": base,
        "quote_asset": quote,
        "min_order_size": Decimal(str(market_data.get("minOrderSize", "0.00001"))),
        "min_price_increment": Decimal(str(market_data.get("tickSize", "0.01"))),
        "min_base_amount_increment": Decimal(str(market_data.get("stepSize", "0.00001"))),
        "min_notional": Decimal(str(market_data.get("minNotional", "1"))),
    }


def format_ws_subscription_message(channel: str, symbol: Optional[str] = None) -> Dict[str, Any]:
    """
    Format a WebSocket subscription message.

    Args:
        channel: Channel name (e.g., "depth", "trade")
        symbol: Trading symbol (optional for some channels)

    Returns:
        Subscription message dict
    """
    if symbol:
        stream = f"{channel}.{symbol}"
    else:
        stream = channel

    return {
        "method": "SUBSCRIBE",
        "params": [stream],
    }


def format_ws_unsubscription_message(channel: str, symbol: Optional[str] = None) -> Dict[str, Any]:
    """
    Format a WebSocket unsubscription message.

    Args:
        channel: Channel name
        symbol: Trading symbol (optional)

    Returns:
        Unsubscription message dict
    """
    if symbol:
        stream = f"{channel}.{symbol}"
    else:
        stream = channel

    return {
        "method": "UNSUBSCRIBE",
        "params": [stream],
    }
