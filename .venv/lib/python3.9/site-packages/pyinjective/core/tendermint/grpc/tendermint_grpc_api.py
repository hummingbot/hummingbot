from typing import Any, Callable, Dict, Optional

from grpc.aio import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.cosmos.base.tendermint.v1beta1 import (
    query_pb2 as tendermint_query,
    query_pb2_grpc as tendermint_query_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class TendermintGrpcApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = tendermint_query_grpc.ServiceStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_node_info(self) -> Dict[str, Any]:
        request = tendermint_query.GetNodeInfoRequest()
        response = await self._execute_call(call=self._stub.GetNodeInfo, request=request)

        return response

    async def fetch_syncing(self) -> Dict[str, Any]:
        request = tendermint_query.GetSyncingRequest()
        response = await self._execute_call(call=self._stub.GetSyncing, request=request)

        return response

    async def fetch_latest_block(self) -> Dict[str, Any]:
        request = tendermint_query.GetLatestBlockRequest()
        response = await self._execute_call(call=self._stub.GetLatestBlock, request=request)

        return response

    async def fetch_block_by_height(self, height: int) -> Dict[str, Any]:
        request = tendermint_query.GetBlockByHeightRequest(height=height)
        response = await self._execute_call(call=self._stub.GetBlockByHeight, request=request)

        return response

    async def fetch_latest_validator_set(self) -> Dict[str, Any]:
        request = tendermint_query.GetLatestValidatorSetRequest()
        response = await self._execute_call(call=self._stub.GetLatestValidatorSet, request=request)

        return response

    async def fetch_validator_set_by_height(
        self, height: int, pagination: Optional[PaginationOption] = None
    ) -> Dict[str, Any]:
        if pagination is None:
            pagination = PaginationOption()
        request = tendermint_query.GetValidatorSetByHeightRequest(
            height=height, pagination=pagination.create_pagination_request()
        )
        response = await self._execute_call(call=self._stub.GetValidatorSetByHeight, request=request)

        return response

    async def abci_query(
        self, path: str, data: Optional[bytes] = None, height: Optional[int] = None, prove: bool = False
    ) -> Dict[str, Any]:
        request = tendermint_query.ABCIQueryRequest(path=path, data=data, height=height, prove=prove)
        response = await self._execute_call(call=self._stub.ABCIQuery, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
