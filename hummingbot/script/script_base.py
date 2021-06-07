import asyncio
import traceback
from multiprocessing import Queue
from typing import List, Optional, Dict, Any, Callable
from decimal import Decimal
from statistics import mean, median
from operator import itemgetter

from .script_interface import (
    OnTick,
    OnStatus,
    OnCommand,
    PMMParameters,
    CallNotify,
    CallLog,
    PmmMarketInfo,
    ScriptError
)
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
        self.max_mid_prices_length: int = 86400  # 60 * 60 * 24 = 1 day of prices
        self.pmm_parameters: PMMParameters = None
        self.pmm_market_info: PmmMarketInfo = None
        # all_total_balances stores balances in {exchange: {token: balance}} format
        # for example {"binance": {"BTC": Decimal("0.1"), "ETH": Decimal("20"}}
        self.all_total_balances: Dict[str, Dict[str, Decimal]] = None
        # all_available_balances has the same data structure as all_total_balances
        self.all_available_balances: Dict[str, Dict[str, Decimal]] = None

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
            try:
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
                    if len(self.mid_prices) > self.max_mid_prices_length:
                        self.mid_prices = self.mid_prices[len(self.mid_prices) - self.max_mid_prices_length:]
                    self.pmm_parameters = item.pmm_parameters
                    self.all_total_balances = item.all_total_balances
                    self.all_available_balances = item.all_available_balances
                    self.on_tick()
                elif isinstance(item, BuyOrderCompletedEvent):
                    self.on_buy_order_completed(item)
                elif isinstance(item, SellOrderCompletedEvent):
                    self.on_sell_order_completed(item)
                elif isinstance(item, OnStatus):
                    status_msg = self.on_status()
                    if status_msg:
                        self.notify(f"Script status: {status_msg}")
                elif isinstance(item, OnCommand):
                    self.on_command(item.cmd, item.args)
                elif isinstance(item, PmmMarketInfo):
                    self.pmm_market_info = item
            except asyncio.CancelledError:
                raise
            except Exception as e:
                # Capturing traceback here and put it as part of ScriptError, which can then be reported in the parent
                # process.
                tb = "".join(traceback.TracebackException.from_exception(e).format())
                self._child_queue.put(ScriptError(e, tb))

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
        samples = self.take_samples(self.mid_prices, interval, length)
        if samples is None:
            return None
        return mean(samples)

    def avg_price_volatility(self, interval: int, length: int) -> Optional[Decimal]:
        """
        Calculates average (mean) price volatility, volatility is a price change compared to the previous
        cycle regardless of its direction, e.g. if price changes -3% (or 3%), the volatility is 3%.
        Examples: To get the average of the last 10 changes on a minute interval = avg_price_volatility(60, 10)
        :param interval: The interval (in seconds) in which to sample the mid prices.
        :param length: The number of the samples to calculate the average.
        :returns None if there is not enough samples, otherwise the average mid price change.
        """
        return self.locate_central_price_volatility(interval, length, mean)

    def median_price_volatility(self, interval: int, length: int) -> Optional[Decimal]:
        """
        Calculates the median (middle value) price volatility, volatility is a price change compared to the previous
        cycle regardless of its direction, e.g. if price changes -3% (or 3%), the volatility is 3%.
        Examples: To get the median of the last 10 changes on a minute interval = median_price_volatility(60, 10)
        :param interval: The interval (in seconds) in which to sample the mid prices.
        :param length: The number of the samples to calculate the average.
        :returns None if there is not enough samples, otherwise the median mid price change.
        """
        return self.locate_central_price_volatility(interval, length, median)

    def locate_central_price_volatility(self, interval: int, length: int, locate_function: Callable) \
            -> Optional[Decimal]:
        """
        Calculates central location of the price volatility, volatility is a price change compared to the previous cycle
        regardless of its direction, e.g. if price changes -3% (or 3%), the volatility is 3%.
        Examples: To get mean of the last 10 changes on a minute interval locate_central_price_volatility(60, 10, mean)
        :param interval: The interval in which to sample the mid prices.
        :param length: The number of the samples.
        :param locate_function: The function used to calculate the central location, e.g. mean, median, geometric_mean
         and many more which are supported by statistics library.
        :returns None if there is not enough samples, otherwise the central location of mid price change.
        """
        # We need sample size of length + 1, as we need a previous value to calculate the change
        samples = self.take_samples(self.mid_prices, interval, length + 1)
        if samples is None:
            return None
        changes = []
        for index in range(1, len(samples)):
            changes.append(max(samples[index], samples[index - 1]) / min(samples[index], samples[index - 1]) - 1)
        return locate_function(changes)

    @staticmethod
    def round_by_step(a_number: Decimal, step_size: Decimal):
        """
        Rounds the number down by the step size, e.g. round_by_step(1.8, 0.25) = 1.75
        :param a_number: A number to round
        :param step_size: The step size.
        :returns rounded number.
        """
        return (a_number // step_size) * step_size

    @staticmethod
    def take_samples(a_list: List[Any], interval: int, length: int) -> Optional[List[any]]:
        """
        Takes samples out of a given list where the last item is the most recent,
        Examples: a list = [1, 2, 3, 4, 5, 6, 7] an interval of 3 and length of 2 will return you [4, 7],
        for an interval of 2 and length of 4, you'll get [1, 3, 5, 7]
        :param a_list: A list which to take samples from
        :param interval: The interval at which to take sample, starting from the last item on the list.
        :param length: The number of the samples.
        :returns None if there is not enough samples to satisfy length, otherwise the sample list.
        """
        index_list = list(range(len(a_list) - 1, -1, -1 * interval))
        index_list = sorted(index_list)
        index_list = index_list[-1 * length:]
        if len(index_list) < length:
            return None
        if len(index_list) == 1:
            # return a list with just 1 item in it.
            return [a_list[index_list[0]]]
        samples = list(itemgetter(*index_list)(a_list))
        return samples

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
        return f"{self.__class__.__name__} is active."

    def on_command(self, cmd: str, args: List[str]):
        """
        Called when 'script' command is issued on the Hummingbot application
        """
        pass
