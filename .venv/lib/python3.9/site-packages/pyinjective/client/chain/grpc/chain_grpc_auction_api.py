from typing import Any, Callable, Dict

from grpc.aio import Channel

from pyinjective.core.network import CookieAssistant
from pyinjective.proto.injective.auction.v1beta1 import (
    query_pb2 as auction_query_pb,
    query_pb2_grpc as auction_query_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class ChainGrpcAuctionApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = auction_query_grpc.QueryStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_module_params(self) -> Dict[str, Any]:
        request = auction_query_pb.QueryAuctionParamsRequest()
        response = await self._execute_call(call=self._stub.AuctionParams, request=request)

        return response

    async def fetch_module_state(self) -> Dict[str, Any]:
        request = auction_query_pb.QueryModuleStateRequest()
        response = await self._execute_call(call=self._stub.AuctionModuleState, request=request)

        return response

    async def fetch_current_basket(self) -> Dict[str, Any]:
        request = auction_query_pb.QueryCurrentAuctionBasketRequest()
        response = await self._execute_call(call=self._stub.CurrentAuctionBasket, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
