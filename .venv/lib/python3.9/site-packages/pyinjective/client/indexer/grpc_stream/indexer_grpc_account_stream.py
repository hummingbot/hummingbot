from typing import Callable, List, Optional

from grpc.aio import Channel

from pyinjective.core.network import CookieAssistant
from pyinjective.proto.exchange import (
    injective_accounts_rpc_pb2 as exchange_accounts_pb,
    injective_accounts_rpc_pb2_grpc as exchange_accounts_grpc,
)
from pyinjective.utils.grpc_api_stream_assistant import GrpcApiStreamAssistant


class IndexerGrpcAccountStream:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = self._stub = exchange_accounts_grpc.InjectiveAccountsRPCStub(channel)
        self._assistant = GrpcApiStreamAssistant(cookie_assistant=cookie_assistant)

    async def stream_subaccount_balance(
        self,
        subaccount_id: str,
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
        denoms: Optional[List[str]] = None,
    ):
        request = exchange_accounts_pb.StreamSubaccountBalanceRequest(
            subaccount_id=subaccount_id,
            denoms=denoms,
        )

        await self._assistant.listen_stream(
            call=self._stub.StreamSubaccountBalance,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )
