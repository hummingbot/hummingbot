from typing import Any, Callable, Dict, Optional

from grpc.aio import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.ibc.applications.transfer.v1 import (
    query_pb2 as ibc_transfer_query,
    query_pb2_grpc as ibc_transfer_query_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class IBCTransferGrpcApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = ibc_transfer_query_grpc.QueryStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_params(self) -> Dict[str, Any]:
        request = ibc_transfer_query.QueryParamsRequest()
        response = await self._execute_call(call=self._stub.Params, request=request)

        return response

    async def fetch_denom_trace(self, hash: str) -> Dict[str, Any]:
        request = ibc_transfer_query.QueryDenomTraceRequest(hash=hash)
        response = await self._execute_call(call=self._stub.DenomTrace, request=request)

        return response

    async def fetch_denom_traces(self, pagination: Optional[PaginationOption] = None) -> Dict[str, Any]:
        if pagination is None:
            pagination = PaginationOption()
        request = ibc_transfer_query.QueryDenomTracesRequest(pagination=pagination.create_pagination_request())
        response = await self._execute_call(call=self._stub.DenomTraces, request=request)

        return response

    async def fetch_denom_hash(self, trace: str) -> Dict[str, Any]:
        request = ibc_transfer_query.QueryDenomHashRequest(trace=trace)
        response = await self._execute_call(call=self._stub.DenomHash, request=request)

        return response

    async def fetch_escrow_address(self, port_id: str, channel_id: str) -> Dict[str, Any]:
        request = ibc_transfer_query.QueryEscrowAddressRequest(port_id=port_id, channel_id=channel_id)
        response = await self._execute_call(call=self._stub.EscrowAddress, request=request)

        return response

    async def fetch_total_escrow_for_denom(self, denom: str) -> Dict[str, Any]:
        request = ibc_transfer_query.QueryTotalEscrowForDenomRequest(denom=denom)
        response = await self._execute_call(call=self._stub.TotalEscrowForDenom, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
