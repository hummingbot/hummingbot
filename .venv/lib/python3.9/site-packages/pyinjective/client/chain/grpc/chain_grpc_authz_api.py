from typing import Any, Callable, Dict, Optional

from grpc.aio import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.cosmos.authz.v1beta1 import query_pb2 as authz_query, query_pb2_grpc as authz_query_grpc
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class ChainGrpcAuthZApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = authz_query_grpc.QueryStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_grants(
        self,
        granter: str,
        grantee: str,
        msg_type_url: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = authz_query.QueryGrantsRequest(
            granter=granter, grantee=grantee, msg_type_url=msg_type_url, pagination=pagination_request
        )

        response = await self._execute_call(call=self._stub.Grants, request=request)

        return response

    async def fetch_granter_grants(
        self,
        granter: str,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = authz_query.QueryGranterGrantsRequest(granter=granter, pagination=pagination_request)

        response = await self._execute_call(call=self._stub.GranterGrants, request=request)

        return response

    async def fetch_grantee_grants(
        self,
        grantee: str,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = authz_query.QueryGranteeGrantsRequest(grantee=grantee, pagination=pagination_request)

        response = await self._execute_call(call=self._stub.GranteeGrants, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
