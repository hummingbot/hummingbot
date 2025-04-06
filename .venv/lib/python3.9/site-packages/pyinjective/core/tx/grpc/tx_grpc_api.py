from typing import Any, Callable, Dict

from grpc.aio import Channel

from pyinjective.core.network import CookieAssistant
from pyinjective.proto.cosmos.tx.v1beta1 import service_pb2 as tx_service, service_pb2_grpc as tx_service_grpc
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class TxGrpcApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = tx_service_grpc.ServiceStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def simulate(self, tx_bytes: bytes) -> Dict[str, Any]:
        request = tx_service.SimulateRequest(tx_bytes=tx_bytes)
        response = await self._execute_call(call=self._stub.Simulate, request=request)

        return response

    async def fetch_tx(self, hash: str) -> Dict[str, Any]:
        request = tx_service.GetTxRequest(hash=hash)
        response = await self._execute_call(call=self._stub.GetTx, request=request)

        return response

    async def broadcast(self, tx_bytes: bytes, mode: int = tx_service.BROADCAST_MODE_ASYNC) -> Dict[str, Any]:
        request = tx_service.BroadcastTxRequest(tx_bytes=tx_bytes, mode=mode)
        response = await self._execute_call(call=self._stub.BroadcastTx, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
