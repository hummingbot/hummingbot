from hummingbot.core.utils.async_utils import safe_ensure_future
import pandas as pd
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class OrderBookCommand:
    def order_book(self,  # type: HummingbotApplication
                   lines: int = 5,
                   exchange: str = None,
                   market: str = None):
        safe_ensure_future(self.show_order_book(lines, exchange, market))

    async def show_order_book(self,  # type: HummingbotApplication
                              lines: int = 5,
                              exchange: str = None,
                              market: str = None):
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
        bids = order_book.snapshot[0][['price', 'amount']].head(lines)
        bids.rename(columns={'price': 'bid_price', 'amount': 'bid_volume'}, inplace=True)
        asks = order_book.snapshot[1][['price', 'amount']].head(lines)
        asks.rename(columns={'price': 'ask_price', 'amount': 'ask_volume'}, inplace=True)
        joined_df = pd.concat([bids, asks], axis=1)
        text_lines = ["    " + line for line in joined_df.to_string(index=False).split("\n")]
        self._notify(f"  market: {market_connector.name} {trading_pair}\n")
        self._notify("\n".join(text_lines))
