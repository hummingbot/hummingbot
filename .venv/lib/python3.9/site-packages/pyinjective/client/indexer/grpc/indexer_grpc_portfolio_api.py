from typing import Any, Callable, Dict

from grpc.aio import Channel

from pyinjective.core.network import CookieAssistant
from pyinjective.proto.exchange import (
    injective_portfolio_rpc_pb2 as exchange_portfolio_pb,
    injective_portfolio_rpc_pb2_grpc as exchange_portfolio_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class IndexerGrpcPortfolioApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = self._stub = exchange_portfolio_grpc.InjectivePortfolioRPCStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_account_portfolio(self, account_address: str) -> Dict[str, Any]:
        request = exchange_portfolio_pb.AccountPortfolioRequest(account_address=account_address)
        response = await self._execute_call(call=self._stub.AccountPortfolio, request=request)

        return response

    async def fetch_account_portfolio_balances(self, account_address: str) -> Dict[str, Any]:
        request = exchange_portfolio_pb.AccountPortfolioBalancesRequest(account_address=account_address)
        response = await self._execute_call(call=self._stub.AccountPortfolioBalances, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
