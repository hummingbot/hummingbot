#!/usr/bin/env python

import logging


from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_py_base import StrategyPyBase

hws_logger = None


class HelloWorldStrategy(StrategyPyBase):
    """
    Simple strategy. This strategy waits for connector to be ready. Displays the user balance of the specified asset when
    the `status` command is executed.
    Note: Strategy is intended to be a developer guide.
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hws_logger
        if hws_logger is None:
            hws_logger = logging.getLogger(__name__)
        return hws_logger

    def __init__(self,
                 exchange: ExchangeBase,
                 trading_pair: str,
                 asset: str):

        super().__init__()
        self._exchange = exchange
        self._asset = asset
        self._ready = False

        self.add_markets([self._exchange])

    async def format_status(self) -> str:
        """
        Method called by the `status` command. Generates the status report for this strategy.
        Simply outputs the balance of the specified asset on the exchange.
        """
        if not self._ready:
            return "Exchange connector(s) are not ready."
        lines = []

        lines.extend(["", "  Assets:"] + ["    " + str(self._asset) + "    " +
                                          str(self._exchange.get_balance(self._asset))])

        return "\n".join(lines)

    def tick(self, timestamp: float):
        """
        Clock tick entry point, it runs every second (on normal tick settings)
        : param timestamp: current tick timestamp
        """
        if self._ready:
            return

        if not self._ready and not self._exchange.ready:
            # Message output using self.logger() will be displayed on Log panel(right) and saved on the strategy's log file.
            self.logger().warning(f"{self._exchange.name} is not ready. Please wait...")
        else:
            self._ready = True
            # Message output using self.notify_hb_app(...) will be displayed on the Output panel(upper left) and not saved on the strategy's log file.
            self.notify_hb_app(f"{self._exchange.name} is ready!")

        return
