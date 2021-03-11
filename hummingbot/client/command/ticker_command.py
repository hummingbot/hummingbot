import pandas as pd
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.event.events import PriceType
from typing import TYPE_CHECKING
import threading

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class TickerCommand:
    def ticker(self,  # type: HummingbotApplication
               live: bool = False,
               exchange: str = None,
               market: str = None):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.ticker, live, exchange, market)
            return
        safe_ensure_future(self.show_ticker(live, exchange, market))

    async def show_ticker(self,  # type: HummingbotApplication
                          live: int = 10,
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

        def get_ticker():
            columns = ["Best Bid", "Best Ask", "Mid Price", "Last Trade"]
            data = [[
                float(market_connector.get_price_by_type(trading_pair, PriceType.BestBid)),
                float(market_connector.get_price_by_type(trading_pair, PriceType.BestAsk)),
                float(market_connector.get_price_by_type(trading_pair, PriceType.MidPrice)),
                float(market_connector.get_price_by_type(trading_pair, PriceType.LastTrade))
            ]]
            ticker_df = pd.DataFrame(data=data, columns=columns).to_string(index=False)
            return f"   Market: {market_connector.name}\n  {ticker_df}"

        if live:
            await self.stop_live_update()
            self.app.live_updates = True
            while self.app.live_updates:
                await self.cls_display_delay(get_ticker() + "\n\n Press escape key to stop update.", 1)
            self._notify("Stopped live ticker display update.")
        else:
            self._notify(get_ticker())
