from typing import TYPE_CHECKING

import pandas as pd

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401

import threading


def order_book_rows(order_book, lines: int):
    """Top-N (bids, asks) DataFrames with price/amount — the shared snapshot extraction."""
    return (order_book.snapshot[0][['price', 'amount']].head(lines),
            order_book.snapshot[1][['price', 'amount']].head(lines))


def format_order_book(order_book, market_name: str, trading_pair: str, lines: int, table_format) -> str:
    """Render top-N order-book depth as an indented table.

    Shared by the interactive ``order_book`` command and the standalone ``hbot order-book`` CLI.
    """
    bids, asks = order_book_rows(order_book, lines)
    bids = bids.rename(columns={'price': 'bid_price', 'amount': 'bid_volume'}).reset_index(drop=True)
    asks = asks.rename(columns={'price': 'ask_price', 'amount': 'ask_volume'}).reset_index(drop=True)
    joined_df = pd.concat([bids, asks], axis=1)
    text_lines = ["    " + line for line in format_df_for_printout(joined_df, table_format).split("\n")]
    return f"  market: {market_name} {trading_pair}\n" + "\n".join(text_lines)


class OrderBookCommand:
    def order_book(self,  # type: HummingbotApplication
                   lines: int = 5,
                   exchange: str = None,
                   market: str = None,
                   live: bool = False):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.order_book, lines, exchange, market, live)
            return
        safe_ensure_future(self.show_order_book(lines, exchange, market, live))

    async def show_order_book(self,  # type: HummingbotApplication
                              lines: int = 5,
                              exchange: str = None,
                              market: str = None,
                              live: bool = False):
        if len(self.trading_core.markets.keys()) == 0:
            self.notify("There is currently no active market.")
            return
        if exchange is not None:
            if exchange not in self.trading_core.markets:
                self.notify("Invalid exchange")
                return
            market_connector = self.trading_core.markets[exchange]
        else:
            market_connector = list(self.trading_core.markets.values())[0]
        if market is not None:
            market = market.upper()
            if market not in market_connector.order_books:
                self.notify("Invalid market")
                return
            trading_pair, order_book = market, market_connector.order_books[market]
        else:
            trading_pair, order_book = next(iter(market_connector.order_books.items()))

        def get_order_book(lines):
            return format_order_book(order_book, market_connector.name, trading_pair, lines,
                                     self.client_config_map.tables_format)

        if live:
            await self.stop_live_update()
            self.app.live_updates = True
            while self.app.live_updates:
                await self.cls_display_delay(get_order_book(min(lines, 35)) + "\n\n Press escape key to stop update.", 0.5)
            self.notify("Stopped live orderbook display update.")
        else:
            self.notify(get_order_book(lines))
