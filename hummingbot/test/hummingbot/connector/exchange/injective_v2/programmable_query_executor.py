import asyncio
from typing import Any, Callable, Dict, List, Optional

from pyinjective.core.market import DerivativeMarket, SpotMarket
from pyinjective.core.token import Token
from pyinjective.proto.injective.stream.v1beta1 import query_pb2 as chain_stream_query

from hummingbot.connector.exchange.injective_v2.injective_query_executor import BaseInjectiveQueryExecutor


class ProgrammableQueryExecutor(BaseInjectiveQueryExecutor):

    def __init__(self):
        self._ping_responses = asyncio.Queue()
        self._spot_markets_responses = asyncio.Queue()
        self._derivative_market_responses = asyncio.Queue()
        self._derivative_markets_responses = asyncio.Queue()
        self._tokens_responses = asyncio.Queue()
        self._spot_order_book_responses = asyncio.Queue()
        self._derivative_order_book_responses = asyncio.Queue()
        self._get_tx_responses = asyncio.Queue()
        self._account_portfolio_responses = asyncio.Queue()
        self._simulate_transaction_responses = asyncio.Queue()
        self._send_transaction_responses = asyncio.Queue()
        self._spot_trades_responses = asyncio.Queue()
        self._derivative_trades_responses = asyncio.Queue()
        self._historical_spot_orders_responses = asyncio.Queue()
        self._historical_derivative_orders_responses = asyncio.Queue()
        self._funding_rates_responses = asyncio.Queue()
        self._oracle_prices_responses = asyncio.Queue()
        self._funding_payments_responses = asyncio.Queue()
        self._derivative_positions_responses = asyncio.Queue()

        self._transaction_events = asyncio.Queue()
        self._chain_stream_events = asyncio.Queue()

    async def ping(self):
        response = await self._ping_responses.get()
        return response

    async def spot_markets(self) -> Dict[str, SpotMarket]:
        response = await self._spot_markets_responses.get()
        return response

    async def derivative_markets(self) -> Dict[str, DerivativeMarket]:
        response = await self._derivative_markets_responses.get()
        return response

    async def tokens(self) -> Dict[str, Token]:
        response = await self._tokens_responses.get()
        return response

    async def derivative_market(self, market_id: str) -> Dict[str, Any]:
        response = await self._derivative_market_responses.get()
        return response

    async def get_spot_orderbook(self, market_id: str) -> Dict[str, Any]:
        response = await self._spot_order_book_responses.get()
        return response

    async def get_derivative_orderbook(self, market_id: str) -> Dict[str, Any]:
        response = await self._derivative_order_book_responses.get()
        return response

    async def get_tx(self, tx_hash: str) -> Dict[str, Any]:
        response = await self._get_tx_responses.get()
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

    async def get_derivative_trades(
            self,
            market_ids: List[str],
            subaccount_id: Optional[str] = None,
            start_time: Optional[int] = None,
            skip: Optional[int] = None,
            limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        response = await self._derivative_trades_responses.get()
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

    async def get_historical_derivative_orders(
            self,
            market_ids: List[str],
            subaccount_id: str,
            start_time: int,
            skip: int,
    ) -> Dict[str, Any]:
        response = await self._historical_derivative_orders_responses.get()
        return response

    async def get_funding_rates(self, market_id: str, limit: int) -> Dict[str, Any]:
        response = await self._funding_rates_responses.get()
        return response

    async def get_funding_payments(self, subaccount_id: str, market_id: str, limit: int) -> Dict[str, Any]:
        response = await self._funding_payments_responses.get()
        return response

    async def get_derivative_positions(self, subaccount_id: str, skip: int) -> Dict[str, Any]:
        response = await self._derivative_positions_responses.get()
        return response

    async def get_oracle_prices(
            self,
            base_symbol: str,
            quote_symbol: str,
            oracle_type: str,
            oracle_scale_factor: int,
    ) -> Dict[str, Any]:
        response = await self._oracle_prices_responses.get()
        return response

    async def listen_transactions_updates(
        self,
        callback: Callable,
        on_end_callback: Callable,
        on_status_callback: Callable,
    ):
        while True:
            next_event = await self._transaction_events.get()
            await callback(next_event)

    async def listen_chain_stream_updates(
        self,
        callback: Callable,
        on_end_callback: Callable,
        on_status_callback: Callable,
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
        while True:
            next_event = await self._chain_stream_events.get()
            await callback(next_event)
