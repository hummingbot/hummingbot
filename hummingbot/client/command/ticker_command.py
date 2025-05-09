import threading
from typing import TYPE_CHECKING

import pandas as pd

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.data_type.common import PriceType
from hummingbot.core.utils.async_utils import safe_ensure_future

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
                          live: bool = False,
                          exchange: str = None,
                          market: str = None):
        if len(self.markets.keys()) == 0:
            self.notify("\n This command can only be used while a strategy is running")
            return
        if exchange is not None:
            if exchange not in self.markets:
                self.notify("\n Please select a valid exchange from the running strategy")
                return
            market_connector = self.markets[exchange]
        else:
            market_connector = list(self.markets.values())[0]
        if market is not None:
            market = market.upper()
            if market not in market_connector.order_books:
                self.notify("\n Please select a valid trading pair from the running strategy")
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
            ticker_df = pd.DataFrame(data=data, columns=columns)
            ticker_df_str = format_df_for_printout(ticker_df, self.client_config_map.tables_format)
            return f"   Market: {market_connector.name}\n{ticker_df_str}"

        if live:
            await self.stop_live_update()
            self.app.live_updates = True
            while self.app.live_updates:
                await self.cls_display_delay(get_ticker() + "\n\n Press escape key to stop update.", 1)
            self.notify("Stopped live ticker display update.")
        else:
            self.notify(get_ticker())
