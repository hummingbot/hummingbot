from hummingbot.script.script_base import ScriptBase
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent
)


class PingPongScript(ScriptBase):
    def __init__(self):
        super().__init__()
        self.ping_pong_balance = 0

    def on_tick(self):
        print(f"ontick {len(self.mid_prices)}: {self.mid_price} ping pong: {self.ping_pong_balance}")
        strategy = self.pmm_parameters
        buys = strategy.order_levels
        sells = strategy.order_levels
        if self.ping_pong_balance > 0:
            buys -= self.ping_pong_balance
            buys = max(0, buys)
        elif self.ping_pong_balance < 0:
            sells -= abs(self.ping_pong_balance)
            sells = max(0, sells)
        strategy.buy_levels = buys
        strategy.sell_levels = sells

    def on_buy_order_completed(self, event: BuyOrderCompletedEvent):
        self.ping_pong_balance += 1

    def on_sell_order_completed(self, event: SellOrderCompletedEvent):
        self.ping_pong_balance -= 1
