from typing import Dict, Set, List
from time import perf_counter
import asyncio
import logging
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.clock import Clock
from hummingbot.logger import HummingbotLogger

lsb_logger = None


class LiteStrategyBase(StrategyPyBase):

    markets: Dict[str, Set[str]]

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global lsb_logger
        if lsb_logger is None:
            lsb_logger = logging.getLogger(__name__)
        return lsb_logger

    def __init__(self, connectors: List[ConnectorBase]):
        super().__init__()
        self.connectors: List[ConnectorBase] = connectors
        self.ready_to_trade: bool = False
        self.tick_size: float = 1.
        self.add_markets(connectors)

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        if not self.ready_to_trade:
            # Check if there are restored orders, they should be canceled before strategy starts.
            self.ready_to_trade = all(ex.ready for ex in self.connectors)
            if not self.ready_to_trade:
                for con in [c for c in self.connectors if not c.ready]:
                    self.logger().warning(f"{con.exchange_name} is not ready. Please wait...")
                return
            else:
                self.logger().info("All connector(s) are ready. Trading started.")

    async def run(self):
        while True:
            start_time = perf_counter()
            await self.on_tick()
            end_time = perf_counter()
            await asyncio.sleep(self.tick_size - (end_time - start_time))

    async def on_tick(self):
        print(perf_counter())
        # raise NotImplementedError

    def start(self, clock: Clock, timestamp: float):
        self.run_task = safe_ensure_future(self.run())

    def stop(self, clock: Clock):
        self.run_task.cancel()
