from hummingbot.core.utils.async_utils import safe_ensure_future
import pandas as pd
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class TickerCommand:
    def ticker(self,  # type: HummingbotApplication
               repeat: int = 10,
               exchange: str = None,
               market: str = None):
        safe_ensure_future(self.show_ticker(repeat, exchange, market))

    async def show_ticker(self,  # type: HummingbotApplication
                          repeat: int = 10,
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

        best_bid = order_book.snapshot[0][['price']].head(1)
        best_ask = order_book.snapshot[1][['price']].head(1)
        mid_price = (best_bid + best_ask) / 2
        last_trade_price = [order_book.last_trade_price]

        best_bid.rename(columns={'price': 'best_bid'}, inplace=True)
        best_ask.rename(columns={'price': 'best_ask'}, inplace=True)
        mid_price.rename(columns={'price': 'mid_price'}, inplace=True)
        joined_df = pd.concat([mid_price, best_bid, best_ask], axis=1)
        joined_df.insert(0, "last_trade_price", last_trade_price, True)
        text_lines = ["    " + line for line in joined_df.to_string(index=False).split("\n")]
        market_pair = f"  market: {market_connector.name} {trading_pair}\n\n"
        self._notify(f"{market_pair}" + "\n".join(text_lines))
