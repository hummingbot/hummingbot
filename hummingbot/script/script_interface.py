from decimal import Decimal


class StrategyParameters:
    def __init__(self, buy_levels: int, sell_levels: int, order_levels: int):
        self.buy_levels = buy_levels
        self.sell_levels = sell_levels
        self.order_levels = order_levels

    def copy(self):
        return StrategyParameters(self.buy_levels, self.sell_levels, self.order_levels)

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and
                self.buy_levels == other.buy_levels and
                self.sell_levels == other.sell_levels and
                self.order_levels == other.order_levels)


class OnTick:
    def __init__(self, mid_price: Decimal, strategy_parameters: StrategyParameters):
        self.mid_price = mid_price
        self.strategy_parameters = strategy_parameters


class OnBuyCompletedEvent:
    pass


class OnSellCompletedEvent:
    pass


class CallUpdateStrategyParameters:
    def __init__(self, strategy_parameters: StrategyParameters):
        self.strategy_parameters = strategy_parameters
        self.return_value = None


class CallNotify:
    def __init__(self, msg):
        self.msg = msg
        self.return_value = None
