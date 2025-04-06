from typing import Any, Callable, Dict, Optional

from grpc import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.ibc.core.client.v1 import query_pb2 as ibc_client_query, query_pb2_grpc as ibc_client_query_grpc
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class IBCClientGrpcApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = ibc_client_query_grpc.QueryStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_client_state(self, client_id: str) -> Dict[str, Any]:
        request = ibc_client_query.QueryClientStateRequest(client_id=client_id)
        response = await self._execute_call(call=self._stub.ClientState, request=request)

        return response

    async def fetch_client_states(self, pagination: Optional[PaginationOption] = None) -> Dict[str, Any]:
        if pagination is None:
            pagination = PaginationOption()
        request = ibc_client_query.QueryClientStatesRequest(pagination=pagination.create_pagination_request())
        response = await self._execute_call(call=self._stub.ClientStates, request=request)

        return response

    async def fetch_consensus_state(
        self,
        client_id: str,
        revision_number: int,
        revision_height: int,
        latest_height: Optional[bool] = None,
    ) -> Dict[str, Any]:
        request = ibc_client_query.QueryConsensusStateRequest(
            client_id=client_id,
            revision_number=revision_number,
            revision_height=revision_height,
            latest_height=latest_height,
        )
        response = await self._execute_call(call=self._stub.ConsensusState, request=request)

        return response

    async def fetch_consensus_states(
        self, client_id: str, pagination: Optional[PaginationOption] = None
    ) -> Dict[str, Any]:
        if pagination is None:
            pagination = PaginationOption()
        request = ibc_client_query.QueryConsensusStatesRequest(
            client_id=client_id, pagination=pagination.create_pagination_request()
        )
        response = await self._execute_call(call=self._stub.ConsensusStates, request=request)

        return response

    async def fetch_consensus_state_heights(
        self, client_id: str, pagination: Optional[PaginationOption] = None
    ) -> Dict[str, Any]:
        if pagination is None:
            pagination = PaginationOption()
        request = ibc_client_query.QueryConsensusStateHeightsRequest(
            client_id=client_id, pagination=pagination.create_pagination_request()
        )
        response = await self._execute_call(call=self._stub.ConsensusStateHeights, request=request)

        return response

    async def fetch_client_status(self, client_id: str) -> Dict[str, Any]:
        request = ibc_client_query.QueryClientStatusRequest(client_id=client_id)
        response = await self._execute_call(call=self._stub.ClientStatus, request=request)

        return response

    async def fetch_client_params(self) -> Dict[str, Any]:
        request = ibc_client_query.QueryClientParamsRequest()
        response = await self._execute_call(call=self._stub.ClientParams, request=request)

        return response

    async def fetch_upgraded_client_state(self) -> Dict[str, Any]:
        request = ibc_client_query.QueryUpgradedClientStateRequest()
        response = await self._execute_call(call=self._stub.UpgradedClientState, request=request)

        return response

    async def fetch_upgraded_consensus_state(self) -> Dict[str, Any]:
        request = ibc_client_query.QueryUpgradedConsensusStateRequest()
        response = await self._execute_call(call=self._stub.UpgradedConsensusState, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
