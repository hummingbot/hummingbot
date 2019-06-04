from decimal import Decimal


cdef class BinanceTradingRule:
    cdef:
        public str symbol
        public object price_tick_size
        public object order_step_size
        public object min_order_size
        public object min_notional_size

    def __init__(self,
                 symbol: str,
                 price_tick_size: Decimal,
                 order_step_size: Decimal,
                 min_order_size: Decimal,
                 min_notional_size: Decimal):
        self.symbol = symbol
        self.price_tick_size = price_tick_size
        self.order_step_size = order_step_size
        self.min_order_size = min_order_size
        self.min_notional_size = min_notional_size

    def __repr__(self) -> str:
        return f"TradingRule(symbol='{self.symbol}', price_tick_size={self.price_tick_size}, " \
               f"order_step_size={self.order_step_size}, min_order_size={self.min_order_size}, " \
               f"min_notional_size={self.min_notional_size})"



cdef class RadarTradingRule:
    cdef:
        public str symbol
        public double min_order_size            # Calculated min base token size based on last trade price
        public double max_order_size            # Calculated max base token size
        public int price_precision              # Maximum precision allowed for the market. Example: 7 (decimal places)
        public int price_decimals               # Max amount of decimals in base token (price)
        public int amount_decimals              # Max amount of decimals in quote token (amount)

    def __init__(self,
                 symbol: str,
                 min_order_size: float,
                 max_order_size: float,
                 price_precision: int,
                 price_decimals: int,
                 amount_decimals: int):
        self.symbol = symbol
        self.min_order_size = min_order_size
        self.max_order_size = max_order_size
        self.price_precision = price_precision
        self.price_decimals = price_decimals
        self.amount_decimals = amount_decimals

    def __repr__(self) -> str:
        return f"TradingRule(symbol='{self.symbol}', min_order_size={self.min_order_size}, " \
               f"max_order_size={self.max_order_size}, price_precision={self.price_precision}, "\
               f"price_decimals={self.price_decimals}, amount_decimals={self.amount_decimals}"


cdef class DDEXTradingRule:
    cdef:
        public str symbol
        public double min_order_size
        public int price_precision              # max amount of significant digits in a price
        public int price_decimals               # max amount of decimals in a price
        public int amount_decimals              # max amount of decimals in an amount
        public bint supports_limit_orders       # if limit order is allowed for this trading pair
        public bint supports_market_orders      # if market order is allowed for this trading pair

    def __init__(self, symbol: str, min_order_size: float, price_precision: int, price_decimals: int,
                 amount_decimals: int, supports_limit_orders: bool, supports_market_orders: bool):
        self.symbol = symbol
        self.min_order_size = min_order_size
        self.price_precision = price_precision
        self.price_decimals = price_decimals
        self.amount_decimals = amount_decimals
        self.supports_limit_orders = supports_limit_orders
        self.supports_market_orders = supports_market_orders

    def __repr__(self) -> str:
        return f"TradingRule(symbol='{self.symbol}', min_order_size={self.min_order_size}, " \
               f"price_precision={self.price_precision}, price_decimals={self.price_decimals}, "\
               f"amount_decimals={self.amount_decimals}, supports_limit_orders={self.supports_limit_orders}, " \
               f"supports_market_orders={self.supports_market_orders}"


cdef class CoinbaseProTradingRule:
    cdef:
        public str symbol
        public object quote_increment
        public object base_min_size
        public object base_max_size
        public bint limit_only

    def __init__(self, symbol: str,
                 quote_increment: Decimal,
                 base_min_size: Decimal,
                 base_max_size: Decimal,
                 limit_only: bool):
        self.symbol = symbol
        self.quote_increment = quote_increment
        self.base_min_size = base_min_size
        self.base_max_size = base_max_size
        self.limit_only = limit_only

    def __repr__(self) -> str:
        return f"TradingRule(symbol='{self.symbol}', quote_increment={self.quote_increment}, " \
               f"base_min_size={self.base_min_size}, base_max_size={self.base_max_size}, limit_only={self.limit_only}"