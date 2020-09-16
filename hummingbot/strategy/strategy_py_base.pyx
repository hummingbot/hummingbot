from typing import List
from hummingbot.strategy.strategy_base cimport StrategyBase
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.clock import Clock

cdef class StrategyPyBase(StrategyBase):
    def __init__(self):
        super().__init__()

    def add_markets(self, markets: List[ConnectorBase]):
        self.c_add_markets(markets)

    def start(self, clock: Clock, timestamp: float):
        StrategyBase.c_start(self, clock, timestamp)

    cdef c_tick(self, double timestamp):
        StrategyBase.c_tick(self, timestamp)
        self.tick(timestamp)

    def tick(self, timestamp: float):
        raise NotImplementedError

    def stop(self, clock: Clock):
        StrategyBase.c_stop(self, clock)
