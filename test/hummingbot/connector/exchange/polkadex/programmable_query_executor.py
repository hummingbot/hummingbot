import asyncio
from typing import Any, Callable, Dict, List

from hummingbot.connector.exchange.polkadex.polkadex_query_executor import BaseQueryExecutor


class ProgrammableQueryExecutor(BaseQueryExecutor):
    def __init__(self):
        self._main_account = None
        self._all_assets_responses = asyncio.Queue()
        self._all_markets_responses = asyncio.Queue()
        self._order_book_snapshots = asyncio.Queue()
        self._recent_trade_responses = asyncio.Queue()
        self._balances_responses = asyncio.Queue()
        self._place_order_responses = asyncio.Queue()
        self._cancel_order_responses = asyncio.Queue()
        self._order_history_responses = asyncio.Queue()
        self._order_responses = asyncio.Queue()
        self._list_orders_responses = asyncio.Queue()
        self._order_fills_responses = asyncio.Queue()

        self._order_book_update_events = asyncio.Queue()
        self._public_trades_update_events = asyncio.Queue()
        self._private_events = asyncio.Queue()

        self._websocket_failure = False
        self._websocket_failure_timestamp = float(0)
        self._restart_initialization = False

    async def all_assets(self):
        response = await self._all_assets_responses.get()
        return response

    async def all_markets(self):
        response = await self._all_markets_responses.get()
        return response

    async def get_orderbook(self, market_symbol: str) -> Dict[str, Any]:
        snapshot = await self._order_book_snapshots.get()
        return snapshot

    async def main_account_from_proxy(self, proxy_account=str) -> str:
        return self._main_account

    async def recent_trade(self, market_symbol: str) -> Dict[str, Any]:
        response = await self._recent_trade_responses.get()
        return response

    async def get_all_balances_by_main_account(self, main_account: str) -> Dict[str, Any]:
        response = await self._balances_responses.get()
        return response

    async def place_order(self, polkadex_order: Dict[str, Any], signature: Dict[str, Any]) -> Dict[str, Any]:
        response = await self._place_order_responses.get()
        return response

    async def cancel_order(
        self,
        order_id: str,
        market_symbol: str,
        main_address: str,
        proxy_address: str,
        signature: Dict[str, Any],
    ) -> Dict[str, Any]:
        response = await self._cancel_order_responses.get()
        return response

    async def list_order_history_by_account(
        self, main_account: str, from_time: float, to_time: float
    ) -> Dict[str, Any]:
        response = await self._order_history_responses.get()
        return response

    async def find_order_by_id(self, order_id: str) -> Dict[str, Any]:
        response = await self._order_responses.get()
        return response

    async def find_order_by_main_account(self, main_account: str, market_symbol: str, order_id: str) -> Dict[str, Any]:
        response = await self._order_responses.get()
        return response

    async def list_open_orders_by_main_account(self, main_account: str) -> Dict[str, Any]:
        response = await self._list_orders_responses.get()
        return response

    async def get_order_fills_by_main_account(
        self, from_timestamp: float, to_timestamp: float, main_account: str
    ) -> List[Dict[str, Any]]:
        response = await self._order_fills_responses.get()
        return response

    async def listen_to_orderbook_updates(self, events_handler: Callable, market_symbol: str):
        while True:
            event = await self._order_book_update_events.get()
            events_handler(event=event, market_symbol=market_symbol)

    async def listen_to_public_trades(self, events_handler: Callable, market_symbol: str):
        while True:
            event = await self._public_trades_update_events.get()
            events_handler(event=event)

    async def listen_to_private_events(self, events_handler: Callable, address: str):
        while True:
            event = await self._private_events.get()
            events_handler(event=event)
