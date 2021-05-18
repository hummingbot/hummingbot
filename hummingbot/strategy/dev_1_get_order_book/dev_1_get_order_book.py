#!/usr/bin/env python

import logging

from typing import (
    Dict,
)

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

gob_logger = None


class GetOrderBookStrategy(StrategyPyBase):
    """
    Simple strategy. This strategy waits for connector to be ready. Displays the live order book as per running
    the `orderbook --live` command.
    Note: Strategy is intended to be a developer guide.
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global gob_logger
        if gob_logger is None:
            gob_logger = logging.getLogger(__name__)
        return gob_logger

    def __init__(self,
                 exchange: ExchangeBase,
                 market_info: Dict[str, MarketTradingPairTuple],
                 trading_pair: str,
                 ):

        super().__init__()
        self._exchange = exchange
        self._market_info = market_info
        self._ready = False

        self.add_markets([self._exchange])
        self._get_order_book_task = None

    def notify_hb_app(self, msg: str):
        """
        Method called to display message on the Output Panel(upper left)
        """
        from hummingbot.client.hummingbot_application import HummingbotApplication
        HummingbotApplication.main_application()._notify(msg)

    async def format_status(self) -> str:
        """
        Method called by the `status` command. Generates the status report for this strategy.
        Outputs the best bid and ask prices for the specified trading
        """
        if not self._ready:
            return "Exchange connector(s) are not ready."
        lines = []

        for market_info in self._market_infos.values():
            lines.extend(["", "  Assets:"] + ["    " + str(self._asset) + "    " +
                                              str(market_info.market.get_balance(self._asset))])

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
            # TODO: Start the live order book tasks

        return
