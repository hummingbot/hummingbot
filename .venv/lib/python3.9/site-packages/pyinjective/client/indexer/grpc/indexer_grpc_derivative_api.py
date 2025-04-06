from typing import Any, Callable, Dict, List, Optional

from grpc.aio import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.exchange import (
    injective_derivative_exchange_rpc_pb2 as exchange_derivative_pb,
    injective_derivative_exchange_rpc_pb2_grpc as exchange_derivative_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class IndexerGrpcDerivativeApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = self._stub = exchange_derivative_grpc.InjectiveDerivativeExchangeRPCStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_markets(
        self,
        market_statuses: Optional[List[str]] = None,
        quote_denom: Optional[str] = None,
    ) -> Dict[str, Any]:
        request = exchange_derivative_pb.MarketsRequest(
            market_statuses=market_statuses,
            quote_denom=quote_denom,
        )
        response = await self._execute_call(call=self._stub.Markets, request=request)

        return response

    async def fetch_market(self, market_id: str) -> Dict[str, Any]:
        request = exchange_derivative_pb.MarketRequest(market_id=market_id)
        response = await self._execute_call(call=self._stub.Market, request=request)

        return response

    async def fetch_binary_options_markets(
        self,
        market_status: Optional[str] = None,
        quote_denom: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.BinaryOptionsMarketsRequest(
            market_status=market_status,
            quote_denom=quote_denom,
            skip=pagination.skip,
            limit=pagination.limit,
        )
        response = await self._execute_call(call=self._stub.BinaryOptionsMarkets, request=request)

        return response

    async def fetch_binary_options_market(self, market_id: str) -> Dict[str, Any]:
        request = exchange_derivative_pb.BinaryOptionsMarketRequest(market_id=market_id)
        response = await self._execute_call(call=self._stub.BinaryOptionsMarket, request=request)

        return response

    async def fetch_orderbook_v2(self, market_id: str) -> Dict[str, Any]:
        request = exchange_derivative_pb.OrderbookV2Request(market_id=market_id)
        response = await self._execute_call(call=self._stub.OrderbookV2, request=request)

        return response

    async def fetch_orderbooks_v2(self, market_ids: List[str]) -> Dict[str, Any]:
        request = exchange_derivative_pb.OrderbooksV2Request(market_ids=market_ids)
        response = await self._execute_call(call=self._stub.OrderbooksV2, request=request)

        return response

    async def fetch_orders(
        self,
        market_ids: Optional[List[str]] = None,
        order_side: Optional[str] = None,
        subaccount_id: Optional[str] = None,
        is_conditional: Optional[str] = None,
        order_type: Optional[str] = None,
        include_inactive: Optional[bool] = None,
        subaccount_total_orders: Optional[bool] = None,
        trade_id: Optional[str] = None,
        cid: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.OrdersRequest(
            market_ids=market_ids,
            order_side=order_side,
            subaccount_id=subaccount_id,
            skip=pagination.skip,
            limit=pagination.limit,
            start_time=pagination.start_time,
            end_time=pagination.end_time,
            is_conditional=is_conditional,
            order_type=order_type,
            include_inactive=include_inactive,
            subaccount_total_orders=subaccount_total_orders,
            trade_id=trade_id,
            cid=cid,
        )

        response = await self._execute_call(call=self._stub.Orders, request=request)

        return response

    async def fetch_positions(
        self,
        market_ids: Optional[List[str]] = None,
        subaccount_id: Optional[str] = None,
        direction: Optional[str] = None,
        subaccount_total_positions: Optional[bool] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.PositionsRequest(
            market_ids=market_ids,
            subaccount_id=subaccount_id,
            skip=pagination.skip,
            limit=pagination.limit,
            start_time=pagination.start_time,
            end_time=pagination.end_time,
            direction=direction,
            subaccount_total_positions=subaccount_total_positions,
        )

        response = await self._execute_call(call=self._stub.Positions, request=request)

        return response

    async def fetch_positions_v2(
        self,
        market_ids: Optional[List[str]] = None,
        subaccount_id: Optional[str] = None,
        direction: Optional[str] = None,
        subaccount_total_positions: Optional[bool] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.PositionsV2Request(
            market_ids=market_ids,
            subaccount_id=subaccount_id,
            skip=pagination.skip,
            limit=pagination.limit,
            start_time=pagination.start_time,
            end_time=pagination.end_time,
            direction=direction,
            subaccount_total_positions=subaccount_total_positions,
        )

        response = await self._execute_call(call=self._stub.PositionsV2, request=request)

        return response

    async def fetch_liquidable_positions(
        self,
        market_id: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.LiquidablePositionsRequest(
            market_id=market_id,
            skip=pagination.skip,
            limit=pagination.limit,
        )

        response = await self._execute_call(call=self._stub.LiquidablePositions, request=request)

        return response

    async def fetch_funding_payments(
        self,
        market_ids: Optional[List[str]] = None,
        subaccount_id: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.FundingPaymentsRequest(
            market_ids=market_ids,
            subaccount_id=subaccount_id,
            skip=pagination.skip,
            limit=pagination.limit,
            end_time=pagination.end_time,
        )

        response = await self._execute_call(call=self._stub.FundingPayments, request=request)

        return response

    async def fetch_funding_rates(
        self,
        market_id: str,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.FundingRatesRequest(
            market_id=market_id,
            skip=pagination.skip,
            limit=pagination.limit,
            end_time=pagination.end_time,
        )

        response = await self._execute_call(call=self._stub.FundingRates, request=request)

        return response

    async def fetch_trades(
        self,
        market_ids: Optional[List[str]] = None,
        subaccount_ids: Optional[List[str]] = None,
        execution_side: Optional[str] = None,
        direction: Optional[str] = None,
        execution_types: Optional[List[str]] = None,
        trade_id: Optional[str] = None,
        account_address: Optional[str] = None,
        cid: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.TradesRequest(
            market_ids=market_ids,
            subaccount_ids=subaccount_ids,
            execution_side=execution_side,
            direction=direction,
            skip=pagination.skip,
            limit=pagination.limit,
            start_time=pagination.start_time,
            end_time=pagination.end_time,
            execution_types=execution_types,
            trade_id=trade_id,
            account_address=account_address,
            cid=cid,
            fee_recipient=fee_recipient,
        )

        response = await self._execute_call(call=self._stub.Trades, request=request)

        return response

    async def fetch_subaccount_orders_list(
        self,
        subaccount_id: str,
        market_id: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.SubaccountOrdersListRequest(
            subaccount_id=subaccount_id,
            market_id=market_id,
            skip=pagination.skip,
            limit=pagination.limit,
        )

        response = await self._execute_call(call=self._stub.SubaccountOrdersList, request=request)

        return response

    async def fetch_subaccount_trades_list(
        self,
        subaccount_id: str,
        market_id: Optional[str] = None,
        execution_type: Optional[str] = None,
        direction: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.SubaccountTradesListRequest(
            subaccount_id=subaccount_id,
            market_id=market_id,
            execution_type=execution_type,
            direction=direction,
            skip=pagination.skip,
            limit=pagination.limit,
        )

        response = await self._execute_call(call=self._stub.SubaccountTradesList, request=request)

        return response

    async def fetch_orders_history(
        self,
        subaccount_id: Optional[str] = None,
        market_ids: Optional[List[str]] = None,
        order_types: Optional[List[str]] = None,
        direction: Optional[str] = None,
        is_conditional: Optional[str] = None,
        state: Optional[str] = None,
        execution_types: Optional[List[str]] = None,
        trade_id: Optional[str] = None,
        active_markets_only: Optional[bool] = None,
        cid: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.OrdersHistoryRequest(
            subaccount_id=subaccount_id,
            skip=pagination.skip,
            limit=pagination.limit,
            order_types=order_types,
            direction=direction,
            start_time=pagination.start_time,
            end_time=pagination.end_time,
            is_conditional=is_conditional,
            state=state,
            execution_types=execution_types,
            market_ids=market_ids,
            trade_id=trade_id,
            active_markets_only=active_markets_only,
            cid=cid,
        )

        response = await self._execute_call(call=self._stub.OrdersHistory, request=request)

        return response

    async def fetch_trades_v2(
        self,
        market_ids: Optional[List[str]] = None,
        subaccount_ids: Optional[List[str]] = None,
        execution_side: Optional[str] = None,
        direction: Optional[str] = None,
        execution_types: Optional[List[str]] = None,
        trade_id: Optional[str] = None,
        account_address: Optional[str] = None,
        cid: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.TradesV2Request(
            market_ids=market_ids,
            subaccount_ids=subaccount_ids,
            execution_side=execution_side,
            direction=direction,
            skip=pagination.skip,
            limit=pagination.limit,
            start_time=pagination.start_time,
            end_time=pagination.end_time,
            execution_types=execution_types,
            trade_id=trade_id,
            account_address=account_address,
            cid=cid,
            fee_recipient=fee_recipient,
        )

        response = await self._execute_call(call=self._stub.TradesV2, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
