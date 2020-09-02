from hummingbot.connector.trading_rule cimport TradingRule

cdef class EterbaseTradingRule(TradingRule):
    cdef:
        public object max_quantity_significant_digits  # Max # of significant digits in a quantity
        public object max_cost_significant_digits      # Max # of significant digits in a cost
        public object max_order_value                  # Max cost value
        public bint supports_stop_limit_orders         # if stop limit order is allowed for this trading pair
        public bint supports_stop_market_orders        # if stpo market order is allowed for this trading pair
