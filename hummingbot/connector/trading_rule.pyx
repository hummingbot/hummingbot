from decimal import Decimal

s_decimal_0 = Decimal(0)
s_decimal_max = Decimal("1e56")
s_decimal_min = Decimal(1) / s_decimal_max


cdef class TradingRule:
    def __init__(self,
                 trading_pair: str,
                 min_order_size: Decimal = s_decimal_0,
                 max_order_size: Decimal = s_decimal_max,
                 min_price_increment: Decimal = s_decimal_min,
                 min_base_amount_increment: Decimal = s_decimal_min,
                 min_quote_amount_increment: Decimal = s_decimal_min,
                 min_notional_size: Decimal = s_decimal_0,
                 min_order_value: Decimal = s_decimal_0,
                 max_price_significant_digits: Decimal = s_decimal_max,
                 supports_limit_orders: bool = True,
                 supports_market_orders: bool = True):
        self.trading_pair = trading_pair
        self.min_order_size = min_order_size
        self.max_order_size = max_order_size
        self.min_price_increment = min_price_increment
        self.min_base_amount_increment = min_base_amount_increment
        self.min_quote_amount_increment = min_quote_amount_increment
        self.min_notional_size = min_notional_size
        self.min_order_value = min_order_value
        self.max_price_significant_digits = max_price_significant_digits
        self.supports_limit_orders = supports_limit_orders
        self.supports_market_orders = supports_market_orders

    def __repr__(self) -> str:
        return f"TradingRule(trading_pair='{self.trading_pair}', " \
               f"min_order_size={self.min_order_size}, " \
               f"max_order_size={self.max_order_size}, " \
               f"min_price_increment={self.min_price_increment}, " \
               f"min_base_amount_increment={self.min_base_amount_increment}), " \
               f"min_quote_amount_increment={self.min_quote_amount_increment}), " \
               f"min_notional_size={self.min_notional_size}), " \
               f"min_order_value={self.min_order_value}), " \
               f"max_price_significant_digits={self.max_price_significant_digits}), " \
               f"supports_limit_orders={self.supports_limit_orders}), " \
               f"supports_market_orders={self.supports_market_orders})"
