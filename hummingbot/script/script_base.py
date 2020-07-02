import asyncio
from multiprocessing import Queue
from typing import List, Optional, Dict
from decimal import Decimal
from statistics import mean
from operator import itemgetter
from .script_interface import OnTick, OnStatus, PMMParameters, CallNotify, CallLog
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent
)


class ScriptBase:
    """
    ScriptBase provides functionality which a script can use to interact with the main HB application.
    A user defined script should derive from this base class to get all its functionality.
    """
    def __init__(self):
        self._parent_queue: Queue = None
        self._child_queue: Queue = None
        self._queue_check_interval: float = 0.0
        self.mid_prices: List[Decimal] = []
        self.pmm_parameters: PMMParameters = None
        # all_total_balances stores balances in {exchange: {token: balance}} format
        # for example {"binance": {"BTC": Decimal("0.1"), "ETH": Decimal("20"}}
        self.all_total_balances: Dict[str, Dict[str, Decimal]] = None

    def assign_init(self, parent_queue: Queue, child_queue: Queue, queue_check_interval: float):
        self._parent_queue = parent_queue
        self._child_queue = child_queue
        self._queue_check_interval = queue_check_interval

    @property
    def mid_price(self):
        """
        The current market mid price (the average of top bid and top ask)
        """
        return self.mid_prices[-1]

    async def run(self):
        asyncio.ensure_future(self.listen_to_parent())

    async def listen_to_parent(self):
        while True:
            if self._parent_queue.empty():
                await asyncio.sleep(self._queue_check_interval)
                continue
            item = self._parent_queue.get()
            # print(f"child gets {str(item)}")
            if item is None:
                # print("child exiting..")
                asyncio.get_event_loop().stop()
                break
            if isinstance(item, OnTick):
                self.mid_prices.append(item.mid_price)
                self.pmm_parameters = item.pmm_parameters
                self.all_total_balances = item.all_total_balances
                self.on_tick()
            elif isinstance(item, BuyOrderCompletedEvent):
                self.on_buy_order_completed(item)
            elif isinstance(item, SellOrderCompletedEvent):
                self.on_sell_order_completed(item)
            elif isinstance(item, OnStatus):
                status_msg = self.on_status()
                self.notify(f"Script status: {status_msg}")

    def notify(self, msg: str):
        """
        Notifies the user, the message will appear on top left panel of HB application.
        If Telegram integration enabled, the message will also be sent to the telegram user.
        :param msg: The message.
        """
        self._child_queue.put(CallNotify(msg))

    def log(self, msg: str):
        """
        Logs message to the strategy log file and display it on Running Logs section of HB.
        :param msg: The message.
        """
        self._child_queue.put(CallLog(msg))

    def avg_mid_price(self, interval: int, length: int) -> Optional[Decimal]:
        """
        Calculates average (mean) of the stored mid prices.
        Mid prices are stored for each tick (second).
        Examples: To get the average of the last 100 minutes mid prices = avg_mid_price(60, 100)
        :param interval: The interval (in seconds) in which to sample the mid prices.
        :param length: The number of the samples to calculate the average.
        :returns None if there is not enough samples, otherwise the average mid price.
        """
        index_list = list(range(len(self.mid_prices) - 1, 0, -1 * interval))
        index_list = sorted(index_list)
        index_list = index_list[-1 * length:]
        if len(index_list) < length:
            return None
        if len(index_list) == 1:
            return self.mid_prices[index_list[0]]
        sampled_mid_prices = list(itemgetter(*index_list)(self.mid_prices))
        return mean(sampled_mid_prices)

    def on_tick(self):
        """
        Is called upon OnTick message received, which is every second on normal HB configuration.
        It is intended to be implemented by the derived class of this class.
        """
        pass

    def on_buy_order_completed(self, event: BuyOrderCompletedEvent):
        """
        Is called upon a buy order is completely filled.
        It is intended to be implemented by the derived class of this class.
        """
        pass

    def on_sell_order_completed(self, event: SellOrderCompletedEvent):
        """
        Is called upon a sell order is completely filled.
        It is intended to be implemented by the derived class of this class.
        """
        pass

    def on_status(self) -> str:
        """
        Is called upon `status` command is issued on the Hummingbot application.
        It is intended to be implemented by the derived class of this class.
        :returns status message.
        """
        return "on_status not implemented."
