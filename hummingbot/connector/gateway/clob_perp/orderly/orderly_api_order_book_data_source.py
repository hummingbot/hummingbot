import asyncio
from typing import Any, Dict, List, Optional
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.connector.gateway.clob_perp.orderly import orderly_constants as constants

class OrderlyAPIOrderBookDataSource:
    def __init__(self, trading_pairs: List[str]):
        self._trading_pairs = trading_pairs

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        """Returns a new order book for Orderly."""
        return OrderBook()

    async def listen_for_subscriptions(self):
        """Connects to Orderly WSS and subscribes to orderbook topics."""
        pass