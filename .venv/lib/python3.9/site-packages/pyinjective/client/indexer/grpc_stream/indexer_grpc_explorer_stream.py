from typing import Callable, Optional

from grpc.aio import Channel

from pyinjective.core.network import CookieAssistant
from pyinjective.proto.exchange import (
    injective_explorer_rpc_pb2 as exchange_explorer_pb,
    injective_explorer_rpc_pb2_grpc as exchange_explorer_grpc,
)
from pyinjective.utils.grpc_api_stream_assistant import GrpcApiStreamAssistant


class IndexerGrpcExplorerStream:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = self._stub = exchange_explorer_grpc.InjectiveExplorerRPCStub(channel)
        self._assistant = GrpcApiStreamAssistant(cookie_assistant=cookie_assistant)

    async def stream_txs(
        self,
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
    ):
        request = exchange_explorer_pb.StreamTxsRequest()

        await self._assistant.listen_stream(
            call=self._stub.StreamTxs,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )

    async def stream_blocks(
        self,
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
    ):
        request = exchange_explorer_pb.StreamBlocksRequest()

        await self._assistant.listen_stream(
            call=self._stub.StreamBlocks,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )
