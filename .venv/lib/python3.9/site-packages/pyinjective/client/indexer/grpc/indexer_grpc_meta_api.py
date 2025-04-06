import time
from typing import Any, Callable, Dict

from grpc.aio import Channel

from pyinjective.core.network import CookieAssistant
from pyinjective.proto.exchange import (
    injective_meta_rpc_pb2 as exchange_meta_pb,
    injective_meta_rpc_pb2_grpc as exchange_meta_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class IndexerGrpcMetaApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = self._stub = exchange_meta_grpc.InjectiveMetaRPCStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_ping(self) -> Dict[str, Any]:
        request = exchange_meta_pb.PingRequest()
        response = await self._execute_call(call=self._stub.Ping, request=request)

        return response

    async def fetch_version(self) -> Dict[str, Any]:
        request = exchange_meta_pb.VersionRequest()
        response = await self._execute_call(call=self._stub.Version, request=request)

        return response

    async def fetch_info(self) -> Dict[str, Any]:
        request = exchange_meta_pb.InfoRequest(timestamp=int(time.time() * 1000))
        response = await self._execute_call(call=self._stub.Info, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
