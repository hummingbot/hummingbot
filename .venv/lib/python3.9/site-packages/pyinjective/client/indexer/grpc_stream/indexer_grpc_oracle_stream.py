from typing import Callable, List, Optional

from grpc.aio import Channel

from pyinjective.core.network import CookieAssistant
from pyinjective.proto.exchange import (
    injective_oracle_rpc_pb2 as exchange_oracle_pb,
    injective_oracle_rpc_pb2_grpc as exchange_oracle_grpc,
)
from pyinjective.utils.grpc_api_stream_assistant import GrpcApiStreamAssistant


class IndexerGrpcOracleStream:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = self._stub = exchange_oracle_grpc.InjectiveOracleRPCStub(channel)
        self._assistant = GrpcApiStreamAssistant(cookie_assistant=cookie_assistant)

    async def stream_oracle_prices(
        self,
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
        base_symbol: Optional[str] = None,
        quote_symbol: Optional[str] = None,
        oracle_type: Optional[str] = None,
    ):
        request = exchange_oracle_pb.StreamPricesRequest(
            base_symbol=base_symbol,
            quote_symbol=quote_symbol,
            oracle_type=oracle_type,
        )

        await self._assistant.listen_stream(
            call=self._stub.StreamPrices,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )

    async def stream_oracle_prices_by_markets(
        self,
        market_ids: List[str],
        callback: Callable,
        on_end_callback: Optional[Callable] = None,
        on_status_callback: Optional[Callable] = None,
    ):
        request = exchange_oracle_pb.StreamPricesByMarketsRequest(
            market_ids=market_ids,
        )

        await self._assistant.listen_stream(
            call=self._stub.StreamPricesByMarkets,
            request=request,
            callback=callback,
            on_end_callback=on_end_callback,
            on_status_callback=on_status_callback,
        )
