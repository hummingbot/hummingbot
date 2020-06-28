from hummingbot.script.script_base import ScriptBase


class PingPongScript(ScriptBase):
    def __init__(self):
        super().__init__()
        self.ping_pong_balance = 0

    def on_tick(self):
        print(f"ontick {len(self.mid_prices)}: {self.mid_price} ping pong: {self.ping_pong_balance}")
        strategy = self.strategy_parameters.copy()
        if self.ping_pong_balance > 0:
            strategy.buy_levels -= self.ping_pong_balance
            strategy.buy_levels = max(0, strategy.buy_levels)
        elif self.ping_pong_balance < 0:
            strategy.sell_levels -= abs(self.ping_pong_balance)
            strategy.sell_levels = max(0, strategy.sell_levels)
        else:
            strategy.buy_levels = strategy.order_levels
            strategy.sell_levels = strategy.order_levels
        if strategy != self.strategy_parameters:
            self.strategy_parameters = strategy
            self.update_strategy_parameters()

    def on_buy_order_completed(self):
        self.ping_pong_balance += 1

    def on_sell_order_completed(self):
        self.ping_pong_balance -= 1
