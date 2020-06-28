from hummingbot.script.script_base import ScriptBase


class PriceBandScript(ScriptBase):
    def __init__(self):
        super().__init__()

    def on_tick(self):
        print(f"ontick {len(self.mid_prices)}: {self.mid_price}")
        strategy = self.strategy_parameters.copy()
        if self.mid_price >= 105:
            strategy.buy_levels = 0
        else:
            strategy.buy_levels = strategy.order_levels
        if self.mid_price <= 95:
            strategy.sell_levels = 0
        else:
            strategy.sell_levels = strategy.order_levels
        if strategy != self.strategy_parameters:
            self.strategy_parameters = strategy
            self.update_strategy_parameters()
