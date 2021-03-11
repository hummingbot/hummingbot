from hummingbot.core.utils.async_utils import safe_ensure_future
import pandas as pd
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication
import threading


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
        if len(self.markets.keys()) == 0:
            self._notify("There is currently no active market.")
            return
        if exchange is not None:
            if exchange not in self.markets:
                self._notify("Invalid exchange")
                return
            market_connector = self.markets[exchange]
        else:
            market_connector = list(self.markets.values())[0]
        if market is not None:
            market = market.upper()
            if market not in market_connector.order_books:
                self._notify("Invalid market")
                return
            trading_pair, order_book = market, market_connector.order_books[market]
        else:
            trading_pair, order_book = next(iter(market_connector.order_books.items()))

        def get_order_book(lines):
            bids = order_book.snapshot[0][['price', 'amount']].head(lines)
            bids.rename(columns={'price': 'bid_price', 'amount': 'bid_volume'}, inplace=True)
            asks = order_book.snapshot[1][['price', 'amount']].head(lines)
            asks.rename(columns={'price': 'ask_price', 'amount': 'ask_volume'}, inplace=True)
            joined_df = pd.concat([bids, asks], axis=1)
            text_lines = ["    " + line for line in joined_df.to_string(index=False).split("\n")]
            header = f"  market: {market_connector.name} {trading_pair}\n"
            return header + "\n".join(text_lines)

        if live:
            await self.stop_live_update()
            self.app.live_updates = True
            while self.app.live_updates:
                await self.cls_display_delay(get_order_book(min(lines, 35)) + "\n\n Press escape key to stop update.", 0.5)
            self._notify("Stopped live orderbook display update.")
        else:
            self._notify(get_order_book(lines))
