from typing import Any, Callable, Dict, Optional

from grpc import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.ibc.core.connection.v1 import (
    query_pb2 as ibc_connection_query,
    query_pb2_grpc as ibc_connection_query_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class IBCConnectionGrpcApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = ibc_connection_query_grpc.QueryStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_connection(self, connection_id: str) -> Dict[str, Any]:
        request = ibc_connection_query.QueryConnectionRequest(connection_id=connection_id)
        response = await self._execute_call(call=self._stub.Connection, request=request)

        return response

    async def fetch_connections(self, pagination: Optional[PaginationOption] = None) -> Dict[str, Any]:
        if pagination is None:
            pagination = PaginationOption()
        request = ibc_connection_query.QueryConnectionsRequest(pagination=pagination.create_pagination_request())
        response = await self._execute_call(call=self._stub.Connections, request=request)

        return response

    async def fetch_client_connections(self, client_id: str) -> Dict[str, Any]:
        request = ibc_connection_query.QueryClientConnectionsRequest(client_id=client_id)
        response = await self._execute_call(call=self._stub.ClientConnections, request=request)

        return response

    async def fetch_connection_client_state(self, connection_id: str) -> Dict[str, Any]:
        request = ibc_connection_query.QueryConnectionClientStateRequest(connection_id=connection_id)
        response = await self._execute_call(call=self._stub.ConnectionClientState, request=request)

        return response

    async def fetch_connection_consensus_state(
        self,
        connection_id: str,
        revision_number: int,
        revision_height: int,
    ) -> Dict[str, Any]:
        request = ibc_connection_query.QueryConnectionConsensusStateRequest(
            connection_id=connection_id,
            revision_number=revision_number,
            revision_height=revision_height,
        )
        response = await self._execute_call(call=self._stub.ConnectionConsensusState, request=request)

        return response

    async def fetch_connection_params(self) -> Dict[str, Any]:
        request = ibc_connection_query.QueryConnectionParamsRequest()
        response = await self._execute_call(call=self._stub.ConnectionParams, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
