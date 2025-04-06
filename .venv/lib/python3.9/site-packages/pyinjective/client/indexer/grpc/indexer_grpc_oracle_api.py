from typing import Any, Callable, Dict, Optional

from grpc.aio import Channel

from pyinjective.core.network import CookieAssistant
from pyinjective.proto.exchange import (
    injective_oracle_rpc_pb2 as exchange_oracle_pb,
    injective_oracle_rpc_pb2_grpc as exchange_oracle_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class IndexerGrpcOracleApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = self._stub = exchange_oracle_grpc.InjectiveOracleRPCStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_oracle_list(self) -> Dict[str, Any]:
        request = exchange_oracle_pb.OracleListRequest()
        response = await self._execute_call(call=self._stub.OracleList, request=request)

        return response

    async def fetch_oracle_price(
        self,
        base_symbol: Optional[str] = None,
        quote_symbol: Optional[str] = None,
        oracle_type: Optional[str] = None,
        oracle_scale_factor: Optional[int] = None,
    ) -> Dict[str, Any]:
        request = exchange_oracle_pb.PriceRequest(
            base_symbol=base_symbol,
            quote_symbol=quote_symbol,
            oracle_type=oracle_type,
            oracle_scale_factor=oracle_scale_factor,
        )
        response = await self._execute_call(call=self._stub.Price, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
