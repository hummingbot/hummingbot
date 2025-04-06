from typing import Any, Callable, Dict

from grpc.aio import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.cosmos.auth.v1beta1 import query_pb2 as auth_query_pb, query_pb2_grpc as auth_query_grpc
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class ChainGrpcAuthApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = auth_query_grpc.QueryStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_module_params(self) -> Dict[str, Any]:
        request = auth_query_pb.QueryParamsRequest()
        response = await self._execute_call(call=self._stub.Params, request=request)

        return response

    async def fetch_account(self, address: str) -> Dict[str, Any]:
        request = auth_query_pb.QueryAccountRequest(address=address)
        response = await self._execute_call(call=self._stub.Account, request=request)

        return response

    async def fetch_accounts(self, pagination_option: PaginationOption) -> Dict[str, Any]:
        request = auth_query_pb.QueryAccountsRequest(pagination=pagination_option.create_pagination_request())
        response = await self._execute_call(call=self._stub.Accounts, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
