#!/usr/bin/env python

import logging
import pandas as pd

from hummingbot.core.clock import Clock
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_py_base import StrategyPyBase

gob_logger = None


class GetOrderBookStrategy(StrategyPyBase):
    """
    Simple strategy. This strategy waits for connector to be ready. Displays the live order book as per running
    the `orderbook --live` command.
    Note: Strategy is intended to be a developer guide. The objective is to demonstrate how to interact with the OrderBook
    of the specified market on the exchange.
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global gob_logger
        if gob_logger is None:
            gob_logger = logging.getLogger(__name__)
        return gob_logger

    def __init__(self,
                 exchange: ExchangeBase,
                 trading_pair: str,
                 hb_app_notification: bool = False
                 ):

        super().__init__()
        self._exchange = exchange
        self._trading_pair = trading_pair
        self._lines = 5

        self.add_markets([self._exchange])

        self._ready = False
        self._get_order_book_task = None

    async def format_status(self) -> str:
        """
        Method called by the `status` command. Generates the status report for this strategy.
        Outputs the best bid and ask prices of the Order Book.
        """
        if not self._ready:
            return "Exchange connector(s) are not ready."

        headers = f"  Market: {self._exchange.name} | {self._trading_pair}\n"

        order_book = self._exchange.order_books[self._trading_pair]

        best_bid = order_book.snapshot[0][['price']].head(1)
        best_bid.rename(columns={'price': 'best_bid_price'}, inplace=True)
        best_ask = order_book.snapshot[1][['price']].head(1)
        best_ask.rename(columns={'price': 'best_ask_price'}, inplace=True)
        joined_df = pd.concat([best_bid, best_ask], axis=1)

        lines = ["    " + line for line in joined_df.to_string(index=False).split("\n")]
        joined_df = pd.concat([best_bid, best_ask], axis=1)

        return headers + "\n".join(lines)

    def get_order_book(self):
        order_book = self._exchange.order_books[self._trading_pair]

        bids = order_book.snapshot[0][['price', 'amount']].head(self._lines)
        bids.rename(columns={'price': 'bid_price', 'amount': 'bid_volume'}, inplace=True)
        asks = order_book.snapshot[1][['price', 'amount']].head(self._lines)
        asks.rename(columns={'price': 'ask_price', 'amount': 'ask_volume'}, inplace=True)
        joined_df = pd.concat([bids, asks], axis=1)
        text_lines = ["    " + line for line in joined_df.to_string(index=False).split("\n")]
        header = f"  Market: {self._exchange.name} | {self._trading_pair}\n"

        return header + "\n".join(text_lines)

    async def show_order_book(self):
        from hummingbot.client.hummingbot_application import HummingbotApplication
        main_app = HummingbotApplication.main_application()

        if self._trading_pair not in self._exchange.order_books:
            self.logger().error(f"Invalid market {self._trading_pair} on {self._exchange.name} connector.")
            raise ValueError(f"Invalid market {self._trading_pair} on {self._exchange.name} connector.")

        await main_app.stop_live_update()
        main_app.app.live_updates = True
        while main_app.app.live_updates:
            await main_app.cls_display_delay(self.get_order_book() + "\n\n Press escape key to stop update.", 0.5)

        # NOTE: Currently there is no way for users to re-trigger the live orderbook display with this strategy.
        self.notify_hb_app("Stopped live orderbook display update. To show live orderbook again, re-run the strategy by running the `stop` and `start` command.")

    def stop(self, clock: Clock):
        """
        Performs the necessary stop process. This function is called after the StrategyBase.c_stop() is called.
        """
        if self._get_order_book_task is not None:
            self._get_order_book_task.cancel()
            self._get_order_book_task = None

    def tick(self, timestamp: float):
        """
        Clock tick entry point, it runs every second (on normal tick settings)
        : param timestamp: current tick timestamp
        """
        if self._ready:
            return

        if not self._ready and not self._exchange.ready:
            # Message output using self.logger() will be displayed on Log panel(right) and saved on the strategy's log file.
            self.logger().warning(f"{self._exchange.name} connector is not ready. Please wait...")
        else:
            # Message output using self.notify_hb_app(...) will be displayed on the Output panel(upper left) and not saved on the strategy's log file.
            self.logger().info(f"{self._exchange.name.upper()} connector is ready!")
            try:
                if self._get_order_book_task is None:
                    self._get_order_book_task = safe_ensure_future(self.show_order_book())
                    self._ready = True
            except Exception:
                self.logger().error("Error starting live order book. ",
                                    exc_info=True)
                self._ready = False

        return
