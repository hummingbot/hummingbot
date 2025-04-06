from typing import Any, Callable, Dict, Optional

from grpc.aio import Channel

from pyinjective.core.network import CookieAssistant
from pyinjective.proto.injective.tokenfactory.v1beta1 import (
    query_pb2 as token_factory_query_pb,
    query_pb2_grpc as token_factory_query_grpc,
    tx_pb2_grpc as token_factory_tx_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class ChainGrpcTokenFactoryApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._query_stub = token_factory_query_grpc.QueryStub(channel)
        self._tx_stub = token_factory_tx_grpc.MsgStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_module_params(self) -> Dict[str, Any]:
        request = token_factory_query_pb.QueryParamsRequest()
        response = await self._execute_call(call=self._query_stub.Params, request=request)

        return response

    async def fetch_denom_authority_metadata(
        self,
        creator: str,
        sub_denom: Optional[str] = None,
    ) -> Dict[str, Any]:
        request = token_factory_query_pb.QueryDenomAuthorityMetadataRequest(
            creator=creator,
            sub_denom=sub_denom,
        )
        response = await self._execute_call(call=self._query_stub.DenomAuthorityMetadata, request=request)

        return response

    async def fetch_denoms_from_creator(self, creator: str) -> Dict[str, Any]:
        request = token_factory_query_pb.QueryDenomsFromCreatorRequest(creator=creator)
        response = await self._execute_call(call=self._query_stub.DenomsFromCreator, request=request)

        return response

    async def fetch_tokenfactory_module_state(self) -> Dict[str, Any]:
        request = token_factory_query_pb.QueryModuleStateRequest()
        response = await self._execute_call(call=self._query_stub.TokenfactoryModuleState, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
