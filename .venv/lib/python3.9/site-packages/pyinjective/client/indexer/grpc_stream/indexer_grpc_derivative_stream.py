from typing import Callable, List, Optional

from grpc.aio import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.exchange import (
    injective_derivative_exchange_rpc_pb2 as exchange_derivative_pb,
    injective_derivative_exchange_rpc_pb2_grpc as exchange_derivative_grpc,
)
from pyinjective.utils.grpc_api_stream_assistant import GrpcApiStreamAssistant


class IndexerGrpcDerivativeStream:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = self._stub = exchange_derivative_grpc.InjectiveDerivativeExchangeRPCStub(channel)
        self._assistant = GrpcApiStreamAssistant(cookie_assistant=cookie_assistant)

    async def stream_market(
        self,
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
        market_ids: Optional[List[str]] = None,
    ):
        request = exchange_derivative_pb.StreamMarketRequest(
            market_ids=market_ids,
        )

        await self._assistant.listen_stream(
            call=self._stub.StreamMarket,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )

    async def stream_orderbook_v2(
        self,
        market_ids: List[str],
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
    ):
        request = exchange_derivative_pb.StreamOrderbookV2Request(market_ids=market_ids)

        await self._assistant.listen_stream(
            call=self._stub.StreamOrderbookV2,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )

    async def stream_orderbook_update(
        self,
        market_ids: List[str],
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
    ):
        request = exchange_derivative_pb.StreamOrderbookUpdateRequest(market_ids=market_ids)

        await self._assistant.listen_stream(
            call=self._stub.StreamOrderbookUpdate,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )

    async def stream_positions(
        self,
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
        market_ids: Optional[List[str]] = None,
        subaccount_ids: Optional[List[str]] = None,
    ):
        request = exchange_derivative_pb.StreamPositionsRequest(market_ids=market_ids, subaccount_ids=subaccount_ids)

        await self._assistant.listen_stream(
            call=self._stub.StreamPositions,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )

    async def stream_orders(
        self,
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
        market_ids: Optional[List[str]] = None,
        order_side: Optional[str] = None,
        subaccount_id: Optional[PaginationOption] = None,
        is_conditional: Optional[str] = None,
        order_type: Optional[str] = None,
        include_inactive: Optional[bool] = None,
        subaccount_total_orders: Optional[bool] = None,
        trade_id: Optional[str] = None,
        cid: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ):
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.StreamOrdersRequest(
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

        await self._assistant.listen_stream(
            call=self._stub.StreamOrders,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )

    async def stream_trades(
        self,
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
        market_ids: Optional[List[str]] = None,
        execution_side: Optional[str] = None,
        direction: Optional[str] = None,
        subaccount_ids: Optional[List[str]] = None,
        execution_types: Optional[List[str]] = None,
        trade_id: Optional[str] = None,
        account_address: Optional[str] = None,
        cid: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ):
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.StreamTradesRequest(
            execution_side=execution_side,
            direction=direction,
            skip=pagination.skip,
            limit=pagination.limit,
            start_time=pagination.start_time,
            end_time=pagination.end_time,
            market_ids=market_ids,
            subaccount_ids=subaccount_ids,
            execution_types=execution_types,
            trade_id=trade_id,
            account_address=account_address,
            fee_recipient=fee_recipient,
            cid=cid,
        )

        await self._assistant.listen_stream(
            call=self._stub.StreamTrades,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )

    async def stream_orders_history(
        self,
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
        subaccount_id: Optional[str] = None,
        market_id: Optional[str] = None,
        order_types: Optional[List[str]] = None,
        direction: Optional[str] = None,
        state: Optional[str] = None,
        execution_types: Optional[List[str]] = None,
    ):
        request = exchange_derivative_pb.StreamOrdersHistoryRequest(
            subaccount_id=subaccount_id,
            market_id=market_id,
            order_types=order_types,
            direction=direction,
            state=state,
            execution_types=execution_types,
        )

        await self._assistant.listen_stream(
            call=self._stub.StreamOrdersHistory,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )

    async def stream_trades_v2(
        self,
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
        market_ids: Optional[List[str]] = None,
        execution_side: Optional[str] = None,
        direction: Optional[str] = None,
        subaccount_ids: Optional[List[str]] = None,
        execution_types: Optional[List[str]] = None,
        trade_id: Optional[str] = None,
        account_address: Optional[str] = None,
        cid: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ):
        pagination = pagination or PaginationOption()
        request = exchange_derivative_pb.StreamTradesV2Request(
            execution_side=execution_side,
            direction=direction,
            skip=pagination.skip,
            limit=pagination.limit,
            start_time=pagination.start_time,
            end_time=pagination.end_time,
            market_ids=market_ids,
            subaccount_ids=subaccount_ids,
            execution_types=execution_types,
            trade_id=trade_id,
            account_address=account_address,
            cid=cid,
            fee_recipient=fee_recipient,
        )

        await self._assistant.listen_stream(
            call=self._stub.StreamTradesV2,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )

    async def stream_positions_v2(
        self,
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
        subaccount_id: Optional[str] = None,
        market_id: Optional[str] = None,
        market_ids: Optional[List[str]] = None,
        subaccount_ids: Optional[List[str]] = None,
        account_address: Optional[str] = None,
    ):
        request = exchange_derivative_pb.StreamPositionsV2Request(
            subaccount_id=subaccount_id,
            market_id=market_id,
            market_ids=market_ids,
            subaccount_ids=subaccount_ids,
            account_address=account_address,
        )

        await self._assistant.listen_stream(
            call=self._stub.StreamPositionsV2,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )
