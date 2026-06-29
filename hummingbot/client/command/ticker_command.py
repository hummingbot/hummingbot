import threading
from typing import TYPE_CHECKING

import pandas as pd

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.data_type.common import PriceType
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


def get_ticker_prices(connector, trading_pair: str) -> dict:
    """best_bid/best_ask/mid/last for a pair, robust to connectors where ``get_price_by_type``
    raises (e.g. some perpetuals): falls back to the order-book snapshot."""
    def via_type(pt):
        try:
            return float(connector.get_price_by_type(trading_pair, pt))
        except Exception:
            return None
    bid, ask = via_type(PriceType.BestBid), via_type(PriceType.BestAsk)
    mid, last = via_type(PriceType.MidPrice), via_type(PriceType.LastTrade)
    if bid is None or ask is None or mid is None:
        try:
            ob = connector.get_order_book(trading_pair)
            bids, asks = ob.snapshot[0], ob.snapshot[1]
            if bid is None and len(bids):
                bid = float(bids.iloc[0]['price'])
            if ask is None and len(asks):
                ask = float(asks.iloc[0]['price'])
            if mid is None and bid is not None and ask is not None:
                mid = (bid + ask) / 2
        except Exception:
            pass
    return {"best_bid": bid, "best_ask": ask, "mid_price": mid, "last_trade": last}


def format_ticker(connector, trading_pair: str, table_format) -> str:
    """Render best bid/ask/mid/last as a one-row table.

    Shared by the interactive ``ticker`` command and the standalone ``hbot ticker`` CLI.
    """
    p = get_ticker_prices(connector, trading_pair)
    df = pd.DataFrame(data=[[p["best_bid"], p["best_ask"], p["mid_price"], p["last_trade"]]],
                      columns=["Best Bid", "Best Ask", "Mid Price", "Last Trade"])
    return f"   Market: {connector.name}\n{format_df_for_printout(df, table_format)}"


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
        if len(self.trading_core.markets.keys()) == 0:
            self.notify("\n This command can only be used while a strategy is running")
            return
        if exchange is not None:
            if exchange not in self.trading_core.markets:
                self.notify("\n Please select a valid exchange from the running strategy")
                return
            market_connector = self.trading_core.markets[exchange]
        else:
            market_connector = list(self.trading_core.markets.values())[0]
        if market is not None:
            market = market.upper()
            if market not in market_connector.order_books:
                self.notify("\n Please select a valid trading pair from the running strategy")
                return
            trading_pair, order_book = market, market_connector.order_books[market]
        else:
            trading_pair, order_book = next(iter(market_connector.order_books.items()))

        def get_ticker():
            return format_ticker(market_connector, trading_pair, self.client_config_map.tables_format)

        if live:
            await self.stop_live_update()
            self.app.live_updates = True
            while self.app.live_updates:
                await self.cls_display_delay(get_ticker() + "\n\n Press escape key to stop update.", 1)
            self.notify("Stopped live ticker display update.")
        else:
            self.notify(get_ticker())
