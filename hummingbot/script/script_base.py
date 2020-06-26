import asyncio
from decimal import Decimal
from multiprocessing import Queue
from .script_interface import CallUpdateStrategyParameters, OnTick, StrategyParameters


class ScriptBase:
    def __init__(self):
        self._parent_queue: Queue = None
        self._child_queue: Queue = None
        self._queue_check_interval: float = 0.0
        self.mid_price: Decimal = Decimal("0")
        self.strategy_parameters: StrategyParameters = None

    def assign_process_init(self, parent_queue: Queue, child_queue: Queue, queue_check_interval: float):
        self._parent_queue = parent_queue
        self._child_queue = child_queue
        self._queue_check_interval = queue_check_interval

    # def on_tick(self):
    #     strategy = self.strategy_parameters.copy()
    #     if self.mid_price >= 105:
    #         strategy.buy_levels = 0
    #     else:
    #         strategy.buy_levels = strategy.order_levels
    #     if self.mid_price <= 95:
    #         strategy.sell_levels = 0
    #     else:
    #         strategy.sell_levels = strategy.order_levels
    #     if strategy != self.strategy_parameters:
    #         self.strategy_parameters = strategy
    #         self.update_strategy_parameters()

    async def run(self):
        asyncio.ensure_future(self.listen_to_parent())

    async def listen_to_parent(self):
        while True:
            if self._parent_queue.empty():
                await asyncio.sleep(0.1)
                continue
            item = self._parent_queue.get()
            print(f"child gets {item.__class__}")
            if item is None:
                print("child exiting..")
                break
            if isinstance(item, OnTick):
                self.mid_price = item.mid_price
                self.strategy_parameters = item.strategy_parameters
                self.on_tick()

    def update_strategy_parameters(self):
        self._child_queue.put(CallUpdateStrategyParameters(self.strategy_parameters))
