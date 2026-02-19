from decimal import Decimal
from typing import Any, Dict
from hummingbot.core.data_type.trading_rule import TradingRule

def build_trading_rule(market_info: Dict[str, Any]) -> TradingRule:
    """
    Converts Decibel market metadata into Hummingbot TradingRule.
    """
    return TradingRule(
        trading_pair=market_info["market_name"],
        min_order_size=Decimal(str(market_info["min_size"])),
        min_price_increment=Decimal(str(market_info["tick_size"])),
        min_base_amount_increment=Decimal(str(market_info["lot_size"])),
        max_leverage=Decimal(str(market_info["max_leverage"])),
        # Precision handled by decimals provided by Decibel
        # Hummingbot usually handles this via increments, but we can store decimals for reference
    )

def convert_from_exchange_price(price: float, decimals: int) -> Decimal:
    return Decimal(str(price)) # Decibel SDK already returns normalized numbers

def convert_from_exchange_size(size: float, decimals: int) -> Decimal:
    return Decimal(str(size))

# Base URL for Aptos Labs Decibel API
TRADING_HTTP_URL = "https://api.mainnet.aptoslabs.com/decibel"
TRADING_WS_URL = "wss://api.mainnet.aptoslabs.com/decibel/ws"
