from hummingbot.script.script_base import ScriptBase
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent
)


class PingPongScript(ScriptBase):
    """
    Demonstrates how to set up a ping pong trading strategy which alternates buy and sell orders.
    If a buy order is filled, there will be one less buy order submitted at the next refresh cycle.
    If a sell order is filled, there will be one less sell order submitted at the next refresh cycle.
    The balance is positive if there are more completed buy orders than sell orders.
    """

    def __init__(self):
        super().__init__()
        self.ping_pong_balance = 0

    def on_tick(self):
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

    def on_status(self):
        # return the current balance here to be displayed when status command is executed.
        return f"ping_pong_balance: {self.ping_pong_balance}"
