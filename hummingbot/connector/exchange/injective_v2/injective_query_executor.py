from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from google.protobuf import json_format
from grpc import RpcError
from pyinjective.async_client import AsyncClient
from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.market import DerivativeMarket, SpotMarket
from pyinjective.core.token import Token
from pyinjective.proto.injective.stream.v1beta1 import query_pb2 as chain_stream_query


class BaseInjectiveQueryExecutor(ABC):

    @abstractmethod
    async def ping(self):
        raise NotImplementedError

    @abstractmethod
    async def spot_markets(self) -> Dict[str, SpotMarket]:
        raise NotImplementedError

    @abstractmethod
    async def derivative_markets(self) -> Dict[str, DerivativeMarket]:
        raise NotImplementedError

    @abstractmethod
    async def tokens(self) -> Dict[str, Token]:
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
    async def transactions_stream(self):  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    async def chain_stream(
            self,
            bank_balances_filter: Optional[chain_stream_query.BankBalancesFilter] = None,
            subaccount_deposits_filter: Optional[chain_stream_query.SubaccountDepositsFilter] = None,
            spot_trades_filter: Optional[chain_stream_query.TradesFilter] = None,
            derivative_trades_filter: Optional[chain_stream_query.TradesFilter] = None,
            spot_orders_filter: Optional[chain_stream_query.OrdersFilter] = None,
            derivative_orders_filter: Optional[chain_stream_query.OrdersFilter] = None,
            spot_orderbooks_filter: Optional[chain_stream_query.OrderbookFilter] = None,
            derivative_orderbooks_filter: Optional[chain_stream_query.OrderbookFilter] = None,
            positions_filter: Optional[chain_stream_query.PositionsFilter] = None,
            oracle_price_filter: Optional[chain_stream_query.OraclePriceFilter] = None,
    ):
        raise NotImplementedError


class PythonSDKInjectiveQueryExecutor(BaseInjectiveQueryExecutor):

    def __init__(self, sdk_client: AsyncClient):
        super().__init__()
        self._sdk_client = sdk_client

    async def ping(self):  # pragma: no cover
        await self._sdk_client.ping()

    async def spot_markets(self) -> Dict[str, SpotMarket]:  # pragma: no cover
        return await self._sdk_client.all_spot_markets()

    async def derivative_markets(self) -> Dict[str, DerivativeMarket]:  # pragma: no cover
        return await self._sdk_client.all_derivative_markets()

    async def tokens(self) -> Dict[str, Token]:  # pragma: no cover
        return await self._sdk_client.all_tokens()

    async def derivative_market(self, market_id: str) -> Dict[str, Any]:  # pragma: no cover
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
        subaccount_ids = [subaccount_id] if subaccount_id is not None else None
        pagination = PaginationOption(skip=skip, limit=limit, start_time=start_time)
        response = await self._sdk_client.fetch_spot_trades(
            market_ids=market_ids,
            subaccount_ids=subaccount_ids,
            pagination=pagination,
        )
        return response

    async def get_derivative_trades(
            self,
            market_ids: List[str],
            subaccount_id: Optional[str] = None,
            start_time: Optional[int] = None,
            skip: Optional[int] = None,
            limit: Optional[int] = None,
    ) -> Dict[str, Any]:  # pragma: no cover
        subaccount_ids = [subaccount_id] if subaccount_id is not None else None
        pagination = PaginationOption(skip=skip, limit=limit, start_time=start_time)
        response = await self._sdk_client.fetch_derivative_trades(
            market_ids=market_ids,
            subaccount_ids=subaccount_ids,
            pagination=pagination,
        )
        return response

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

    async def transactions_stream(self):  # pragma: no cover
        stream = await self._sdk_client.stream_txs()
        async for event in stream:
            yield json_format.MessageToDict(event)

    async def chain_stream(
        self,
        bank_balances_filter: Optional[chain_stream_query.BankBalancesFilter] = None,
        subaccount_deposits_filter: Optional[chain_stream_query.SubaccountDepositsFilter] = None,
        spot_trades_filter: Optional[chain_stream_query.TradesFilter] = None,
        derivative_trades_filter: Optional[chain_stream_query.TradesFilter] = None,
        spot_orders_filter: Optional[chain_stream_query.OrdersFilter] = None,
        derivative_orders_filter: Optional[chain_stream_query.OrdersFilter] = None,
        spot_orderbooks_filter: Optional[chain_stream_query.OrderbookFilter] = None,
        derivative_orderbooks_filter: Optional[chain_stream_query.OrderbookFilter] = None,
        positions_filter: Optional[chain_stream_query.PositionsFilter] = None,
        oracle_price_filter: Optional[chain_stream_query.OraclePriceFilter] = None,
    ):  # pragma: no cover
        stream = await self._sdk_client.chain_stream(
            bank_balances_filter=bank_balances_filter,
            subaccount_deposits_filter=subaccount_deposits_filter,
            spot_trades_filter=spot_trades_filter,
            derivative_trades_filter=derivative_trades_filter,
            spot_orders_filter=spot_orders_filter,
            derivative_orders_filter=derivative_orders_filter,
            spot_orderbooks_filter=spot_orderbooks_filter,
            derivative_orderbooks_filter=derivative_orderbooks_filter,
            positions_filter=positions_filter,
            oracle_price_filter=oracle_price_filter,
        )
        async for event in stream:
            yield json_format.MessageToDict(event, including_default_value_fields=True)
