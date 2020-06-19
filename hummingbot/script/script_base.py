import asyncio
from decimal import Decimal
from .script_interface import CallUpdateStrategyParameters, OnTick


class ScriptBase:
    def __init__(self, parent_queue, child_queue):
        print("ScriptBase__init__")
        self._parent_queue = parent_queue
        self._child_queue = child_queue
        self.mid_price = Decimal("0")
        self.strategy_parameters = None

    def on_tick(self):
        print("on_tick")
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

    async def run(self):
        asyncio.ensure_future(self.listen_to_parent())

    async def listen_to_parent(self):
        while True:
            if self._parent_queue.empty():
                await asyncio.sleep(0.1)
                continue
            item = self._parent_queue.get()
            print(f"child gets {item.__class__}")
            if isinstance(item, OnTick):
                self.mid_price = item.mid_price
                self.strategy_parameters = item.strategy_parameters
                self.on_tick()

    def update_strategy_parameters(self):
        self._child_queue.put(CallUpdateStrategyParameters(self.strategy_parameters))
