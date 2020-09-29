import pandas as pd
import asyncio
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.event.events import PriceType
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
            self._notify("\n This command can only be used while a strategy is running")
            return
        if exchange is not None:
            if exchange not in self.markets:
                self._notify("\n Please select a valid exchange from the running strategy")
                return
            market_connector = self.markets[exchange]
        else:
            market_connector = list(self.markets.values())[0]
        if market is not None:
            market = market.upper()
            if market not in market_connector.order_books:
                self._notify("\n Please select a valid trading pair from the running strategy")
                return
            trading_pair, order_book = market, market_connector.order_books[market]
        else:
            trading_pair, order_book = next(iter(market_connector.order_books.items()))
            self._notify(f"  market: {market_connector.name}")

        # Display market ticker x number of times based on repeat value
        for i in range(repeat):
            columns = ["Best Bid", "Best Ask", "Mid Price", "Last Trade"]
            data = [[
                float(market_connector.get_price_by_type(trading_pair, PriceType.BestBid)),
                float(market_connector.get_price_by_type(trading_pair, PriceType.BestAsk)),
                float(market_connector.get_price_by_type(trading_pair, PriceType.MidPrice)),
                float(market_connector.get_price_by_type(trading_pair, PriceType.LastTrade))
            ]]
            ticker_df = pd.DataFrame(data=data, columns=columns).to_string(index=False)
            self._notify(f"\n  {ticker_df}")
            await asyncio.sleep(1)
