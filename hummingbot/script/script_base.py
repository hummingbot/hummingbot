import asyncio
from multiprocessing import Queue
from typing import List
from decimal import Decimal
from .script_interface import OnTick, OnBuyOrderCompletedEvent, OnSellOrderCompletedEvent, StrategyParameters, \
    CallUpdateStrategyParameters


class ScriptBase:
    def __init__(self):
        self._parent_queue: Queue = None
        self._child_queue: Queue = None
        self._queue_check_interval: float = 0.0
        self.mid_prices: List[Decimal] = []
        self.strategy_parameters: StrategyParameters = None

    def assign_process_init(self, parent_queue: Queue, child_queue: Queue, queue_check_interval: float):
        self._parent_queue = parent_queue
        self._child_queue = child_queue
        self._queue_check_interval = queue_check_interval

    @property
    def mid_price(self):
        return self.mid_prices[-1]

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
                self.mid_prices.append(item.mid_price)
                self.strategy_parameters = item.strategy_parameters
                self.on_tick()
            elif isinstance(item, OnBuyOrderCompletedEvent):
                self.on_buy_order_completed()
            elif isinstance(item, OnSellOrderCompletedEvent):
                self.on_sell_order_completed()

    def on_tick(self):
        raise NotImplementedError

    def on_buy_order_completed(self):
        raise NotImplementedError

    def on_sell_order_completed(self):
        raise NotImplementedError

    def update_strategy_parameters(self):
        self._child_queue.put(CallUpdateStrategyParameters(self.strategy_parameters))
