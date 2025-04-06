class Denom:
    def __init__(
        self,
        description: str,
        base: int,
        quote: int,
        min_price_tick_size: float,
        min_quantity_tick_size: float,
        min_notional: float,
    ):
        self.description = description
        self.base = base
        self.quote = quote
        self.min_price_tick_size = min_price_tick_size
        self.min_quantity_tick_size = min_quantity_tick_size
        self.min_notional = min_notional
