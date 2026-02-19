class TradingRule:
    def __init__(self, trading_pair, min_order_size, min_price_increment, min_base_amount_increment, max_leverage):
        self.trading_pair = trading_pair
        self.min_order_size = min_order_size
        self.min_price_increment = min_price_increment
        self.min_base_amount_increment = min_base_amount_increment
        self.max_leverage = max_leverage
