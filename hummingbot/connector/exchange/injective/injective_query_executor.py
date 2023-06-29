import collections
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from google.protobuf import json_format
from pyinjective.async_client import AsyncClient


class BaseInjectiveQueryExecutor(ABC):

    @abstractmethod
    async def spot_markets(self, status: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_spot_orderbook(self, market_id: str) -> Dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def spot_order_book_updates_stream(self, market_ids: List[str]) -> collections.AsyncIterable:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def public_spot_trades_stream(self, market_ids: List[str]) -> collections.AsyncIterable:
        raise NotImplementedError  # pragma: no cover


class PythonSDKInjectiveQueryExecutor(BaseInjectiveQueryExecutor):

    def __init__(self, sdk_client: AsyncClient):
        super().__init__()
        self._sdk_client = sdk_client

    async def spot_markets(self, status: str) -> List[Dict[str, Any]]:
        response = await self._sdk_client.get_spot_markets(status=status)
        markets = []

        for market_info in response.markets:
            markets.append(json_format.MessageToDict(market_info))

        return markets

    async def get_spot_orderbook(self, market_id: str) -> Dict[str, Any]:
        order_book_response = await self._sdk_client.get_spot_orderbookV2(market_id=market_id)
        order_book_data = order_book_response.orderbook
        result = {
            "buys": [(buy.price, buy.quantity, buy.timestamp) for buy in order_book_data.buys],
            "sells": [(buy.price, buy.quantity, buy.timestamp) for buy in order_book_data.sells],
            "sequence": order_book_data.sequence,
            "timestamp": order_book_data.timestamp,
        }

        return result

    async def spot_order_book_updates_stream(self, market_ids: List[str]) -> collections.AsyncIterable:
        stream = await self._sdk_client.stream_spot_orderbook_update(market_ids=market_ids)
        async for update in stream:
            order_book_update = update.orderbook_level_updates
            yield json_format.MessageToDict(order_book_update)

    async def public_spot_trades_stream(self, market_ids: List[str]) -> collections.AsyncIterable:
        stream = await self._sdk_client.stream_spot_trades(market_ids=market_ids)
        async for trade in stream:
            trade_data = trade.trade
            yield json_format.MessageToDict(trade_data)
