import logging
from decimal import Decimal
from typing import (
    Any,
    Dict,
    List,
)

"""
price tick size = quote quantum =
max_price_decimals = DDEX.price_decimals = Radar.price_precision =
min_base_amount_increment = DDEX.amount_decimals = Radar.price_decimals
min_quote_amount_increment = Radar.amount_decimals
max_price_significant_digits = DDEX.price_precision
Coinbase.quote_increment is another representation of max_price_decimals  e.g. 0.01 can be represented with max_price_decimals
"""


s_decimal_0 = Decimal(0)
s_decimal_max = Decimal("1e56")
s_decimal_min = Decimal(1) / s_decimal_max


cdef class TradingRule:
    def __init__(self,
                 symbol: str,
                 min_order_size: Decimal = s_decimal_0,
                 max_order_size: Decimal = s_decimal_max,
                 min_price_increment: Decimal = s_decimal_min,
                 min_base_amount_increment: Decimal = s_decimal_min,
                 min_quote_amount_increment: Decimal = s_decimal_min,
                 min_notional_size: Decimal = s_decimal_0,
                 max_price_significant_digits: Decimal = s_decimal_max,
                 supports_limit_orders: bool = True,
                 supports_market_orders: bool = True):
        self.symbol = symbol
        self.min_order_size = min_order_size
        self.max_order_size = max_order_size
        self.min_price_increment = min_price_increment
        self.min_base_amount_increment = min_base_amount_increment
        self.min_quote_amount_increment = min_quote_amount_increment
        self.min_notional_size = min_notional_size
        self.max_price_significant_digits = max_price_significant_digits
        self.supports_limit_orders = supports_limit_orders
        self.supports_market_orders = supports_market_orders

    def __repr__(self) -> str:
        return f"TradingRule(symbol='{self.symbol}', " \
               f"min_order_size={self.min_order_size}, " \
               f"max_order_size={self.max_order_size}, " \
               f"min_price_increment={self.min_price_increment}, " \
               f"min_base_amount_increment={self.min_base_amount_increment}), " \
               f"min_quote_amount_increment={self.min_quote_amount_increment}), " \
               f"min_notional_size={self.min_notional_size}), " \
               f"max_price_significant_digits={self.max_price_significant_digits}), " \
               f"supports_limit_orders={self.supports_limit_orders}), " \
               f"supports_market_orders={self.supports_market_orders})"

    @classmethod
    def parse_binance_market_info(cls, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        cdef:
            list symbol_rules = exchange_info_dict.get("symbols", [])
            list retval = []
        for rule in symbol_rules:
            try:
                symbol = rule.get("symbol")
                filters = rule.get("filters")
                price_filter = [f for f in filters if f.get("filterType") == "PRICE_FILTER"][0]
                lot_size_filter = [f for f in filters if f.get("filterType") == "LOT_SIZE"][0]
                min_notional_filter = [f for f in filters if f.get("filterType") == "MIN_NOTIONAL"][0]

                tick_size = price_filter.get("tickSize")
                step_size = Decimal(lot_size_filter.get("stepSize"))
                min_order_size = Decimal(lot_size_filter.get("minQty"))
                min_notional = Decimal(min_notional_filter.get("minNotional"))

                retval.append(
                    TradingRule(symbol,
                                min_order_size=min_order_size,
                                min_price_increment=Decimal(tick_size),
                                min_base_amount_increment=Decimal(step_size),
                                min_notional_size=Decimal(min_notional)))

            except Exception:
                # TODO: REFACTOR
                logging.getLogger().error(f"Error parsing the symbol rule {rule}. Skipping.", exc_info=True)
        return retval

    @classmethod
    def parse_radar_relay_market_info(cls, markets: List[Dict[str, Any]]) -> List[TradingRule]:
        cdef:
            list retval = []
        for market in markets:
            try:
                symbol = market["id"]
                base_token_decimals = market['baseTokenDecimals']
                quote_token_decimals = market['quoteTokenDecimals']
                quote_increment = market["quoteIncrement"]
                min_price_increment = Decimal(f"1e-{quote_increment}")
                min_base_amount_increment = Decimal(f"1e-{base_token_decimals}")
                min_quote_amount_increment = Decimal(f"1e-{quote_token_decimals}")
                retval.append(TradingRule(market["id"],
                                          min_order_size=Decimal(market["minOrderSize"]),
                                          max_order_size=Decimal(market["maxOrderSize"]),
                                          min_price_increment=min_price_increment,
                                          min_base_amount_increment=min_base_amount_increment,
                                          min_quote_amount_increment=min_quote_amount_increment))
            except Exception:
                logging.getLogger().error(f"Error parsing the symbol rule {symbol}. Skipping.", exc_info=True)
        return retval

# cdef class RadarTradingRule:
#     cdef:
#         public int price_precision              # Maximum precision allowed for the market. Example: 7 (decimal places)

