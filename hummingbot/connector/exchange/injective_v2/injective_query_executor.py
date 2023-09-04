from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from google.protobuf import json_format
from grpc import RpcError
from pyinjective.async_client import AsyncClient


class BaseInjectiveQueryExecutor(ABC):

    @abstractmethod
    async def ping(self):
        raise NotImplementedError

    @abstractmethod
    async def spot_markets(self, status: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def derivative_markets(self, status: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def derivative_market(self, market_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_spot_orderbook(self, market_id: str) -> Dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def get_derivative_orderbook(self, market_id: str) -> Dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def get_tx_by_hash(self, tx_hash: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_tx_block_height(self, tx_hash: str) -> int:
        raise NotImplementedError

    @abstractmethod
    async def account_portfolio(self, account_address: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def simulate_tx(self, tx_byte: bytes) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def send_tx_sync_mode(self, tx_byte: bytes) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_spot_trades(
            self,
            market_ids: List[str],
            subaccount_id: Optional[str] = None,
            start_time: Optional[int] = None,
            skip: Optional[int] = None,
            limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_derivative_trades(
            self,
            market_ids: List[str],
            subaccount_id: Optional[str] = None,
            start_time: Optional[int] = None,
            skip: Optional[int] = None,
            limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_historical_spot_orders(
            self,
            market_ids: List[str],
            subaccount_id: str,
            start_time: int,
            skip: int,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_historical_derivative_orders(
            self,
            market_ids: List[str],
            subaccount_id: str,
            start_time: int,
            skip: int,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_funding_rates(self, market_id: str, limit: int) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_oracle_prices(
            self,
            base_symbol: str,
            quote_symbol: str,
            oracle_type: str,
            oracle_scale_factor: int,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_funding_payments(self, subaccount_id: str, market_id: str, limit: int) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_derivative_positions(self, subaccount_id: str, skip: int) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def spot_order_book_updates_stream(self, market_ids: List[str]):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def public_spot_trades_stream(self, market_ids: List[str]):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def derivative_order_book_updates_stream(self, market_ids: List[str]):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def public_derivative_trades_stream(self, market_ids: List[str]):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def oracle_prices_stream(self, oracle_base: str, oracle_quote: str, oracle_type: str):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def subaccount_positions_stream(self, subaccount_id: str):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def subaccount_balance_stream(self, subaccount_id: str):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    async def subaccount_historical_spot_orders_stream(
        self, market_id: str, subaccount_id: str
    ):
        raise NotImplementedError

    @abstractmethod
    async def subaccount_historical_derivative_orders_stream(
            self, market_id: str, subaccount_id: str
    ):
        raise NotImplementedError

    @abstractmethod
    async def transactions_stream(self):  # pragma: no cover
        raise NotImplementedError


class PythonSDKInjectiveQueryExecutor(BaseInjectiveQueryExecutor):

    def __init__(self, sdk_client: AsyncClient):
        super().__init__()
        self._sdk_client = sdk_client

    async def ping(self):  # pragma: no cover
        await self._sdk_client.ping()

    async def spot_markets(self, status: str) -> List[Dict[str, Any]]:  # pragma: no cover
        response = await self._sdk_client.get_spot_markets(status=status)
        markets = []

        for market_info in response.markets:
            markets.append(json_format.MessageToDict(market_info))

        return markets

    async def derivative_markets(self, status: str) -> List[Dict[str, Any]]:  # pragma: no cover
        response = await self._sdk_client.get_derivative_markets(status=status)
        markets = []

        for market_info in response.markets:
            markets.append(json_format.MessageToDict(market_info))

        return markets

    async def derivative_market(self, market_id: str) -> List[Dict[str, Any]]:  # pragma: no cover
        response = await self._sdk_client.get_derivative_market(market_id=market_id)
        market = json_format.MessageToDict(response.market)

        return market

    async def get_spot_orderbook(self, market_id: str) -> Dict[str, Any]:  # pragma: no cover
        order_book_response = await self._sdk_client.get_spot_orderbookV2(market_id=market_id)
        order_book_data = order_book_response.orderbook
        result = {
            "buys": [(buy.price, buy.quantity, buy.timestamp) for buy in order_book_data.buys],
            "sells": [(buy.price, buy.quantity, buy.timestamp) for buy in order_book_data.sells],
            "sequence": order_book_data.sequence,
            "timestamp": order_book_data.timestamp,
        }

        return result

    async def get_derivative_orderbook(self, market_id: str) -> Dict[str, Any]:  # pragma: no cover
        order_book_response = await self._sdk_client.get_derivative_orderbooksV2(market_ids=[market_id])
        order_book_data = order_book_response.orderbooks[0].orderbook
        result = {
            "buys": [(buy.price, buy.quantity, buy.timestamp) for buy in order_book_data.buys],
            "sells": [(buy.price, buy.quantity, buy.timestamp) for buy in order_book_data.sells],
            "sequence": order_book_data.sequence,
            "timestamp": order_book_data.timestamp,
        }

        return result

    async def get_tx_by_hash(self, tx_hash: str) -> Dict[str, Any]:  # pragma: no cover
        try:
            transaction_response = await self._sdk_client.get_tx_by_hash(tx_hash=tx_hash)
        except RpcError as rpc_exception:
            if "object not found" in str(rpc_exception):
                raise ValueError(f"The transaction with hash {tx_hash} was not found")
            else:
                raise

        result = json_format.MessageToDict(transaction_response)
        return result

    async def get_tx_block_height(self, tx_hash: str) -> int:  # pragma: no cover
        try:
            transaction_response = await self._sdk_client.get_tx(tx_hash=tx_hash)
        except RpcError as rpc_exception:
            if "StatusCode.NOT_FOUND" in str(rpc_exception):
                raise ValueError(f"The transaction with hash {tx_hash} was not found")
            else:
                raise

        result = transaction_response.tx_response.height
        return result

    async def account_portfolio(self, account_address: str) -> Dict[str, Any]:  # pragma: no cover
        portfolio_response = await self._sdk_client.get_account_portfolio(account_address=account_address)
        result = json_format.MessageToDict(portfolio_response.portfolio)
        return result

    async def simulate_tx(self, tx_byte: bytes) -> Dict[str, Any]:  # pragma: no cover
        response, success = await self._sdk_client.simulate_tx(tx_byte=tx_byte)
        if not success:
            raise RuntimeError(f"Transaction simulation failure ({response})")
        result = json_format.MessageToDict(response)
        return result

    async def send_tx_sync_mode(self, tx_byte: bytes) -> Dict[str, Any]:  # pragma: no cover
        response = await self._sdk_client.send_tx_sync_mode(tx_byte=tx_byte)
        result = json_format.MessageToDict(response)
        return result

    async def get_spot_trades(
            self,
            market_ids: List[str],
            subaccount_id: Optional[str] = None,
            start_time: Optional[int] = None,
            skip: Optional[int] = None,
            limit: Optional[int] = None,
    ) -> Dict[str, Any]:  # pragma: no cover
        response = await self._sdk_client.get_spot_trades(
            market_ids=market_ids,
            subaccount_id=subaccount_id,
            start_time=start_time,
            skip=skip,
            limit=limit,
        )
        result = json_format.MessageToDict(response)
        return result

    async def get_derivative_trades(
            self,
            market_ids: List[str],
            subaccount_id: Optional[str] = None,
            start_time: Optional[int] = None,
            skip: Optional[int] = None,
            limit: Optional[int] = None,
    ) -> Dict[str, Any]:  # pragma: no cover
        response = await self._sdk_client.get_derivative_trades(
            market_ids=market_ids,
            subaccount_id=subaccount_id,
            start_time=start_time,
            skip=skip,
            limit=limit,
        )
        result = json_format.MessageToDict(response)
        return result

    async def get_historical_spot_orders(
            self,
            market_ids: List[str],
            subaccount_id: str,
            start_time: int,
            skip: int,
    ) -> Dict[str, Any]:  # pragma: no cover
        response = await self._sdk_client.get_historical_spot_orders(
            market_ids=market_ids,
            subaccount_id=subaccount_id,
            start_time=start_time,
            skip=skip,
        )
        result = json_format.MessageToDict(response)
        return result

    async def get_historical_derivative_orders(
            self,
            market_ids: List[str],
            subaccount_id: str,
            start_time: int,
            skip: int,
    ) -> Dict[str, Any]:  # pragma: no cover
        response = await self._sdk_client.get_historical_derivative_orders(
            market_ids=market_ids,
            subaccount_id=subaccount_id,
            start_time=start_time,
            skip=skip,
        )
        result = json_format.MessageToDict(response)
        return result

    async def get_funding_rates(self, market_id: str, limit: int) -> Dict[str, Any]:
        response = await self._sdk_client.get_funding_rates(market_id=market_id, limit=limit)
        result = json_format.MessageToDict(response)
        return result

    async def get_funding_payments(self, subaccount_id: str, market_id: str, limit: int) -> Dict[str, Any]:
        response = await self._sdk_client.get_funding_payments(
            subaccount_id=subaccount_id,
            market_id=market_id,
            limit=limit
        )
        result = json_format.MessageToDict(response)
        return result

    async def get_derivative_positions(self, subaccount_id: str, skip: int) -> Dict[str, Any]:
        response = await self._sdk_client.get_derivative_positions(
            subaccount_id=subaccount_id, skip=skip
        )
        result = json_format.MessageToDict(response)
        return result

    async def get_oracle_prices(
            self,
            base_symbol: str,
            quote_symbol: str,
            oracle_type: str,
            oracle_scale_factor: int,
    ) -> Dict[str, Any]:
        response = await self._sdk_client.get_oracle_prices(
            base_symbol=base_symbol,
            quote_symbol=quote_symbol,
            oracle_type=oracle_type,
            oracle_scale_factor=oracle_scale_factor
        )
        result = json_format.MessageToDict(response)
        return result

    async def spot_order_book_updates_stream(self, market_ids: List[str]):  # pragma: no cover
        stream = await self._sdk_client.stream_spot_orderbook_update(market_ids=market_ids)
        async for update in stream:
            order_book_update = update.orderbook_level_updates
            yield json_format.MessageToDict(order_book_update)

    async def public_spot_trades_stream(self, market_ids: List[str]):  # pragma: no cover
        stream = await self._sdk_client.stream_spot_trades(market_ids=market_ids)
        async for trade in stream:
            trade_data = trade.trade
            yield json_format.MessageToDict(trade_data)

    async def derivative_order_book_updates_stream(self, market_ids: List[str]):  # pragma: no cover
        stream = await self._sdk_client.stream_derivative_orderbook_update(market_ids=market_ids)
        async for update in stream:
            order_book_update = update.orderbook_level_updates
            yield json_format.MessageToDict(order_book_update)

    async def public_derivative_trades_stream(self, market_ids: List[str]):  # pragma: no cover
        stream = await self._sdk_client.stream_derivative_trades(market_ids=market_ids)
        async for trade in stream:
            trade_data = trade.trade
            yield json_format.MessageToDict(trade_data)

    async def oracle_prices_stream(self, oracle_base: str, oracle_quote: str, oracle_type: str):  # pragma: no cover
        stream = await self._sdk_client.stream_oracle_prices(
            base_symbol=oracle_base, quote_symbol=oracle_quote, oracle_type=oracle_type
        )
        async for update in stream:
            yield json_format.MessageToDict(update)

    async def subaccount_positions_stream(self, subaccount_id: str):  # pragma: no cover
        stream = await self._sdk_client.stream_derivative_positions(subaccount_id=subaccount_id)
        async for event in stream:
            event_data = event.position
            yield json_format.MessageToDict(event_data)

    async def subaccount_balance_stream(self, subaccount_id: str):  # pragma: no cover
        stream = await self._sdk_client.stream_subaccount_balance(subaccount_id=subaccount_id)
        async for event in stream:
            yield json_format.MessageToDict(event)

    async def subaccount_historical_spot_orders_stream(
        self, market_id: str, subaccount_id: str
    ):  # pragma: no cover
        stream = await self._sdk_client.stream_historical_spot_orders(market_id=market_id, subaccount_id=subaccount_id)
        async for event in stream:
            event_data = event.order
            yield json_format.MessageToDict(event_data)

    async def subaccount_historical_derivative_orders_stream(
        self, market_id: str, subaccount_id: str
    ):  # pragma: no cover
        stream = await self._sdk_client.stream_historical_derivative_orders(market_id=market_id, subaccount_id=subaccount_id)
        async for event in stream:
            event_data = event.order
            yield json_format.MessageToDict(event_data)

    async def transactions_stream(self):  # pragma: no cover
        stream = await self._sdk_client.stream_txs()
        async for event in stream:
            yield json_format.MessageToDict(event)
