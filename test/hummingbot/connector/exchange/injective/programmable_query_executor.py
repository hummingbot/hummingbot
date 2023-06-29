import asyncio
import collections
from typing import Any, Dict, List

from hummingbot.connector.exchange.injective.injective_query_executor import BaseInjectiveQueryExecutor


class ProgrammableQueryExecutor(BaseInjectiveQueryExecutor):

    def __init__(self):
        self._spot_markets_responses = asyncio.Queue()
        self._spot_order_book_responses = asyncio.Queue()

        self._spot_order_book_updates = asyncio.Queue()
        self._public_spot_trade_updates = asyncio.Queue()

    async def spot_markets(self, status: str) -> Dict[str, Any]:
        response = await self._spot_markets_responses.get()
        return response

    async def get_spot_orderbook(self, market_id: str) -> Dict[str, Any]:
        response = await self._spot_order_book_responses.get()
        return response

    async def spot_order_book_updates_stream(self, market_ids: List[str]) -> collections.AsyncIterable:
        while True:
            next_ob_update = await self._spot_order_book_updates.get()
            yield next_ob_update

    async def public_spot_trades_stream(self, market_ids: List[str]) -> collections.AsyncIterable:
        while True:
            next_trade = await self._public_spot_trade_updates.get()
            yield next_trade
