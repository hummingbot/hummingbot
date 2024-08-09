import asyncio
from typing import Any, Callable, Dict, Literal

from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_formatter import DataFormatter
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor import BaseRPCExecutor


class MockRPCExecutor(BaseRPCExecutor):
    def __init__(self):
        self._get_open_orders_responses = asyncio.Queue()
        self._all_assets_responses = asyncio.Queue()
        self._all_markets_responses = asyncio.Queue()
        self._order_book_snapshots = asyncio.Queue()
        self._balances_responses = asyncio.Queue()
        self._place_order_responses = asyncio.Queue()
        self._cancel_order_responses = asyncio.Queue()
        self._order_fills_responses = asyncio.Queue()
        self._get_market_price_responses = asyncio.Queue()

        self._listen_to_market_price_responses = asyncio.Queue()
        self._chain_config = CONSTANTS.DEFAULT_CHAIN_CONFIG
        self._address = ""  # look for an address in the response
        self._check_connection_response = asyncio.Queue()

    async def start(self):
        pass

    async def check_connection_status(self):
        response = await self._check_connection_response.get()
        return response

    async def all_assets(self):
        response = await self._all_assets_responses.get()
        data = DataFormatter.format_all_assets_response(response, chain_config=self._chain_config)
        return data

    async def all_markets(self):
        response = await self._all_markets_responses.get()
        return response

    async def get_orderbook(
        self, base_asset: Dict[str, str], quote_asset: Dict[str, str], orders: int = 20
    ) -> Dict[str, Any]:
        snapshot = await self._order_book_snapshots.get()
        data = DataFormatter.format_orderbook_response(snapshot, base_asset, quote_asset)
        return data

    async def get_open_orders(self, base_asset: Dict[str, str], quote_asset: Dict[str, str]) -> str:
        response = self._get_open_orders_responses.get()
        data = DataFormatter.format_order_response(response, base_asset, quote_asset)
        return data

    async def place_limit_order(
        self, base_asset: str, quote_asset: str, order_id: str, side: Literal["buy", "sell"], sell_amount: int
    ):
        response = await self._place_order_responses.get()
        data = DataFormatter.format_order_response(response, base_asset, quote_asset)
        return data

    async def get_all_balances(self, main_account: str) -> Dict[str, Any]:
        response = await self._balances_responses.get()
        data = DataFormatter.format_balance_response(response)
        return data

    async def get_account_order_fills(self):
        response = await self._order_fills_responses.get()
        all_assets = await self.all_assets()
        data = DataFormatter.format_order_fills_response(response, self._address, all_assets)
        return data

    async def cancel_order(
        self,
        base_asset: str,
        quote_asset: str,
        order_id: str,
        side: Literal["buy", "sell"],
    ):
        response = await self._cancel_order_responses.get()
        data = DataFormatter.format_order_response(response, base_asset, quote_asset)
        return data

    async def get_market_price(self, base_asset: Dict[str, str], quote_asset: Dict[str, str]):
        response = await self._get_market_price_responses.get()
        data = DataFormatter.format_market_price(response)
        return data

    async def listen_to_order_fills(self, events_handler):
        all_assets = await self.all_assets()
        while True:
            event = await self._order_fills_responses.get()
            data = DataFormatter.format_order_fills_response(event, self._address, all_assets)
            events_handler(data)

    async def listen_to_market_price_updates(self, events_handler: Callable, market_symbol: str):
        while True:
            event = await self._listen_to_market_price_responses.get()
            data = DataFormatter.format_market_price(event)
            events_handler(data)
