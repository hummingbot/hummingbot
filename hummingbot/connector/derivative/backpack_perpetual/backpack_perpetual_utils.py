"""
Utility functions for Backpack Perpetual connector.
"""

from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema


# Backpack perpetual trading fees
# Maker: 0.02%, Taker: 0.04%
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0004"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDC"

BROKER_ID = "HBOT"


class BackpackPerpetualConfigMap(BaseConnectorConfigMap):
    """Configuration map for Backpack Perpetual connector."""
    connector: str = "backpack_perpetual"
    backpack_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Backpack API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    backpack_perpetual_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Backpack API secret (ED25519 private key)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="backpack_perpetual")


KEYS = BackpackPerpetualConfigMap.model_construct()

# No other domains for now
OTHER_DOMAINS = []
OTHER_DOMAINS_PARAMETER = {}
OTHER_DOMAINS_EXAMPLE_PAIR = {}
OTHER_DOMAINS_DEFAULT_FEES = {}
OTHER_DOMAINS_KEYS = {}


def is_exchange_information_valid(exchange_info: dict) -> bool:
    """
    Check if exchange info response from Backpack is valid for perpetual trading.

    Args:
        exchange_info: Response from the markets endpoint

    Returns:
        True if the response contains valid perpetual market data
    """
    return (
        exchange_info is not None
        and isinstance(exchange_info, list)
        and len(exchange_info) > 0
    )


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    """
    Convert Hummingbot trading pair format to Backpack perpetual format.

    Args:
        hb_trading_pair: Trading pair in Hummingbot format (e.g., "BTC-USDC")

    Returns:
        Trading pair in Backpack perpetual format (e.g., "BTC_USDC_PERP")
    """
    # Replace hyphen with underscore and add _PERP suffix if not present
    exchange_pair = hb_trading_pair.replace("-", "_")
    if not exchange_pair.endswith("_PERP"):
        exchange_pair = f"{exchange_pair}_PERP"
    return exchange_pair


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    """
    Convert Backpack perpetual format to Hummingbot trading pair format.

    Args:
        exchange_trading_pair: Trading pair in Backpack perpetual format (e.g., "BTC_USDC_PERP")

    Returns:
        Trading pair in Hummingbot format (e.g., "BTC-USDC")
    """
    # Remove _PERP suffix and replace underscore with hyphen
    pair = exchange_trading_pair
    if pair.endswith("_PERP"):
        pair = pair[:-5]  # Remove "_PERP"
    return pair.replace("_", "-")


def decimal_val_or_none(val) -> Decimal | None:
    """
    Convert a value to Decimal or return None if invalid.

    Args:
        val: Value to convert

    Returns:
        Decimal value or None
    """
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except Exception:
        return None


def get_position_side_from_direction(direction: str) -> str:
    """
    Convert Backpack position direction to Hummingbot position side.

    Args:
        direction: Position direction from Backpack ("long" or "short")

    Returns:
        Position side for Hummingbot
    """
    return "LONG" if direction.lower() == "long" else "SHORT"


def calculate_liquidation_price(
    entry_price: Decimal,
    position_size: Decimal,
    margin: Decimal,
    is_long: bool,
    maintenance_margin_rate: Decimal = Decimal("0.005"),
) -> Decimal:
    """
    Estimate liquidation price for a position.

    This is an approximation - actual liquidation price depends on
    exchange-specific rules and current funding rates.

    Args:
        entry_price: Entry price of the position
        position_size: Size of the position (positive for long, negative for short)
        margin: Margin/collateral for the position
        is_long: True if long position, False if short
        maintenance_margin_rate: Maintenance margin rate (default 0.5%)

    Returns:
        Estimated liquidation price
    """
    if position_size == Decimal("0") or margin == Decimal("0"):
        return Decimal("0")

    abs_size = abs(position_size)
    notional = entry_price * abs_size

    if is_long:
        # For long: liq_price = entry_price * (1 - (margin / notional) + maintenance_margin_rate)
        liq_price = entry_price * (Decimal("1") - (margin / notional) + maintenance_margin_rate)
    else:
        # For short: liq_price = entry_price * (1 + (margin / notional) - maintenance_margin_rate)
        liq_price = entry_price * (Decimal("1") + (margin / notional) - maintenance_margin_rate)

    return max(Decimal("0"), liq_price)
