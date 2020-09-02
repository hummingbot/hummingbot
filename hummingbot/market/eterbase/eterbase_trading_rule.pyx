from decimal import Decimal
from hummingbot.connector.trading_rule cimport TradingRule

s_decimal_0 = Decimal(0)
s_decimal_max = Decimal("1e56")
s_decimal_min = Decimal(1) / s_decimal_max

cdef class EterbaseTradingRule(TradingRule):
    def __init__(self,
                 trading_pair: str,
                 min_order_size: Decimal = s_decimal_0,
                 max_order_size: Decimal = s_decimal_max,
                 min_price_increment: Decimal = s_decimal_min,
                 min_base_amount_increment: Decimal = s_decimal_min,
                 min_quote_amount_increment: Decimal = s_decimal_min,
                 min_notional_size: Decimal = s_decimal_0,
                 min_order_value: Decimal = s_decimal_0,
                 max_order_value: Decimal = s_decimal_max,
                 max_price_significant_digits: Decimal = s_decimal_max,
                 max_quantity_significant_digits: Decimal = s_decimal_max,
                 max_cost_significant_digits: Decimal = s_decimal_max,
                 supports_limit_orders: bool = True,
                 supports_market_orders: bool = True,
                 supports_stop_limit_orders: bool = False,
                 supports_stop_market_orders: bool = False):
        super().__init__(trading_pair = trading_pair,
                         min_order_size = min_order_size,
                         max_order_size = max_order_size,
                         min_price_increment = min_price_increment,
                         min_base_amount_increment = min_base_amount_increment,
                         min_quote_amount_increment = min_quote_amount_increment,
                         min_notional_size = min_notional_size,
                         min_order_value = min_order_value,
                         max_price_significant_digits = max_price_significant_digits,
                         supports_limit_orders = supports_limit_orders,
                         supports_market_orders = supports_market_orders)

        self.max_order_value = max_order_value
        self.max_quantity_significant_digits = max_quantity_significant_digits
        self.max_cost_significant_digits = max_cost_significant_digits
        self.supports_stop_limit_orders = supports_stop_limit_orders
        self.supports_stop_market_orders = supports_stop_market_orders

    def __repr__(self) -> str:
        return super().__repr__() + \
            f".EterbaseExtension(" \
            f"max_order_value(cost)={self.max_order_value}, " \
            f"max_quantity_significant_digits={self.max_quantity_significant_digits}, " \
            f"max_cost_significant_digits={self.max_cost_significant_digits}, " \
            f"supports_stop_limit_orders={self.supports_stop_limit_orders}, " \
            f"supports_stop_market_orders={self.supports_stop_market_orders})"
