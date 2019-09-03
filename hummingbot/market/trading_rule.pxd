cdef class TradingRule:
    cdef:
        public str symbol
        public object min_order_size                   # Calculated min base asset size based on last trade price
        public object max_order_size                   # Calculated max base asset size
        public object min_price_increment              # Min tick size difference accepted (e.g. 0.1)
        public object min_base_amount_increment        # Min step size of base asset amount (e.g. 0.01)
        public object min_quote_amount_increment       # Min step size of quote asset amount (e.g. 0.01)
        public object max_price_significant_digits     # Max # of significant digits in a price
        public object min_notional_size                # Notional value = price * quantity, min accepted (e.g. 3.001)
        public bint supports_limit_orders              # if limit order is allowed for this trading pair
        public bint supports_market_orders             # if market order is allowed for this trading pair