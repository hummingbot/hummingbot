from typing import Any, Callable, Dict, Optional

from grpc.aio import Channel

from pyinjective.core.network import CookieAssistant
from pyinjective.proto.exchange import (
    injective_insurance_rpc_pb2 as exchange_insurance_pb,
    injective_insurance_rpc_pb2_grpc as exchange_insurance_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class IndexerGrpcInsuranceApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = self._stub = exchange_insurance_grpc.InjectiveInsuranceRPCStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_insurance_funds(self) -> Dict[str, Any]:
        request = exchange_insurance_pb.FundsRequest()
        response = await self._execute_call(call=self._stub.Funds, request=request)

        return response

    async def fetch_redemptions(
        self,
        address: Optional[str] = None,
        denom: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        request = exchange_insurance_pb.RedemptionsRequest(
            redeemer=address,
            redemption_denom=denom,
            status=status,
        )
        response = await self._execute_call(call=self._stub.Redemptions, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
