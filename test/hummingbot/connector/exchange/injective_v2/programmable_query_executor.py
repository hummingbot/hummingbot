import asyncio
from typing import Any, Dict, List, Optional

from hummingbot.connector.exchange.injective_v2.injective_query_executor import BaseInjectiveQueryExecutor


class ProgrammableQueryExecutor(BaseInjectiveQueryExecutor):

    def __init__(self):
        self._ping_responses = asyncio.Queue()
        self._spot_markets_responses = asyncio.Queue()
        self._spot_order_book_responses = asyncio.Queue()
        self._transaction_by_hash_responses = asyncio.Queue()
        self._account_portfolio_responses = asyncio.Queue()
        self._simulate_transaction_responses = asyncio.Queue()
        self._send_transaction_responses = asyncio.Queue()
        self._spot_trades_responses = asyncio.Queue()
        self._historical_spot_orders_responses = asyncio.Queue()
        self._transaction_block_height_responses = asyncio.Queue()

        self._spot_order_book_updates = asyncio.Queue()
        self._public_spot_trade_updates = asyncio.Queue()
        self._subaccount_balance_events = asyncio.Queue()
        self._historical_spot_order_events = asyncio.Queue()
        self._transaction_events = asyncio.Queue()

    async def ping(self):
        response = await self._ping_responses.get()
        return response

    async def spot_markets(self, status: str) -> Dict[str, Any]:
        response = await self._spot_markets_responses.get()
        return response

    async def get_spot_orderbook(self, market_id: str) -> Dict[str, Any]:
        response = await self._spot_order_book_responses.get()
        return response

    async def get_tx_by_hash(self, tx_hash: str) -> Dict[str, Any]:
        response = await self._transaction_by_hash_responses.get()
        return response

    async def get_tx_block_height(self, tx_hash: str) -> int:
        response = await self._transaction_block_height_responses.get()
        return response

    async def account_portfolio(self, account_address: str) -> Dict[str, Any]:
        response = await self._account_portfolio_responses.get()
        return response

    async def simulate_tx(self, tx_byte: bytes) -> Dict[str, Any]:
        response = await self._simulate_transaction_responses.get()
        return response

    async def send_tx_sync_mode(self, tx_byte: bytes) -> Dict[str, Any]:
        response = await self._send_transaction_responses.get()
        return response

    async def get_spot_trades(
            self,
            market_ids: List[str],
            subaccount_id: Optional[str] = None,
            start_time: Optional[int] = None,
            skip: Optional[int] = None,
            limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        response = await self._spot_trades_responses.get()
        return response

    async def get_historical_spot_orders(
            self,
            market_ids: List[str],
            subaccount_id: str,
            start_time: int,
            skip: int,
    ) -> Dict[str, Any]:
        response = await self._historical_spot_orders_responses.get()
        return response

    async def spot_order_book_updates_stream(self, market_ids: List[str]):
        while True:
            next_ob_update = await self._spot_order_book_updates.get()
            yield next_ob_update

    async def public_spot_trades_stream(self, market_ids: List[str]):
        while True:
            next_trade = await self._public_spot_trade_updates.get()
            yield next_trade

    async def subaccount_balance_stream(self, subaccount_id: str):
        while True:
            next_event = await self._subaccount_balance_events.get()
            yield next_event

    async def subaccount_historical_spot_orders_stream(
        self, market_id: str, subaccount_id: str
    ):
        while True:
            next_event = await self._historical_spot_order_events.get()
            yield next_event

    async def transactions_stream(self,):
        while True:
            next_event = await self._transaction_events.get()
            yield next_event
