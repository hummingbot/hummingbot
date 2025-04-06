from typing import Callable, Optional

from grpc.aio import Channel

from pyinjective.core.network import CookieAssistant
from pyinjective.proto.exchange import (
    injective_portfolio_rpc_pb2 as exchange_portfolio_pb,
    injective_portfolio_rpc_pb2_grpc as exchange_portfolio_grpc,
)
from pyinjective.utils.grpc_api_stream_assistant import GrpcApiStreamAssistant


class IndexerGrpcPortfolioStream:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = self._stub = exchange_portfolio_grpc.InjectivePortfolioRPCStub(channel)
        self._assistant = GrpcApiStreamAssistant(cookie_assistant=cookie_assistant)

    async def stream_account_portfolio(
        self,
        account_address: str,
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
        subaccount_id: Optional[str] = None,
        update_type: Optional[str] = None,
    ):
        request = exchange_portfolio_pb.StreamAccountPortfolioRequest(
            account_address=account_address,
            subaccount_id=subaccount_id,
            type=update_type,
        )

        await self._assistant.listen_stream(
            call=self._stub.StreamAccountPortfolio,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )
