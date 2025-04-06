from typing import Any, Callable, Dict

from grpc.aio import Channel

from pyinjective.core.network import CookieAssistant
from pyinjective.proto.exchange import (
    injective_auction_rpc_pb2 as exchange_auction_pb,
    injective_auction_rpc_pb2_grpc as exchange_auction_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class IndexerGrpcAuctionApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = self._stub = exchange_auction_grpc.InjectiveAuctionRPCStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_auction(self, round: int) -> Dict[str, Any]:
        request = exchange_auction_pb.AuctionEndpointRequest(round=round)
        response = await self._execute_call(call=self._stub.AuctionEndpoint, request=request)

        return response

    async def fetch_auctions(self) -> Dict[str, Any]:
        request = exchange_auction_pb.AuctionsRequest()
        response = await self._execute_call(call=self._stub.Auctions, request=request)

        return response

    async def fetch_inj_burnt(self) -> Dict[str, Any]:
        request = exchange_auction_pb.InjBurntEndpointRequest()
        response = await self._execute_call(call=self._stub.InjBurntEndpoint, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
