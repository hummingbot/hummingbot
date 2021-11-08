import asyncio
import pandas as pd

from typing import TYPE_CHECKING, Dict, Any
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication

from hummingbot.client.ui.custom_widgets import CustomTextArea
from .tab_base import TabBase


class OrderBookTab(TabBase):
    @classmethod
    def get_command_name(cls) -> str:
        return "order_book"

    @classmethod
    def get_command_help_message(cls) -> str:
        return "Display current order book"

    @classmethod
    def get_command_arguments(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "--lines": {'type': int, 'default': 5, 'dest': "lines", 'help': "Number of lines to display"},
            "--exchange": {'type': str, 'dest': "exchange", 'help': "The exchange of the market"},
            "--market": {'type': str, 'dest': "market", 'help': "The market (trading pair) of the order book"},
            "--live": {'default': False, 'action': "store_true", 'dest': "live", 'help': "Show order book updates"}
        }

    @classmethod
    async def display(cls,
                      output_field: CustomTextArea,
                      hummingbot: "HummingbotApplication",
                      lines: int = 5,
                      exchange: str = None,
                      market: str = None,
                      live: bool = False):
        if len(hummingbot.markets.keys()) == 0:
            output_field.log("There is currently no active market.")
            return
        if exchange is not None:
            if exchange not in hummingbot.markets:
                output_field.log("Invalid exchange")
                return
            market_connector = hummingbot.markets[exchange]
        else:
            market_connector = list(hummingbot.markets.values())[0]
        if market is not None:
            market = market.upper()
            if market not in market_connector.order_books:
                output_field.log("Invalid market")
                return
            trading_pair, order_book = market, market_connector.order_books[market]
        else:
            trading_pair, order_book = next(iter(market_connector.order_books.items()))

        def get_order_book_text(no_lines: int):
            bids = order_book.snapshot[0][['price', 'amount']].head(no_lines)
            bids.rename(columns={'price': 'bid_price', 'amount': 'bid_volume'}, inplace=True)
            asks = order_book.snapshot[1][['price', 'amount']].head(no_lines)
            asks.rename(columns={'price': 'ask_price', 'amount': 'ask_volume'}, inplace=True)
            joined_df = pd.concat([bids, asks], axis=1)
            text_lines = ["" + line for line in joined_df.to_string(index=False).split("\n")]
            header = f"market: {market_connector.name} {trading_pair}\n"
            return header + "\n".join(text_lines)

        if live:
            while True:
                order_book_text = get_order_book_text(min(lines, 35))
                output_field.log(order_book_text, save_log=False)
                await asyncio.sleep(0.5)
        else:
            output_field.log(get_order_book_text(lines))
