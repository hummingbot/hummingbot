from typing import Any, Callable, Dict, List, Optional

from grpc import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.ibc.core.channel.v1 import (
    query_pb2 as ibc_channel_query,
    query_pb2_grpc as ibc_channel_query_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class IBCChannelGrpcApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = ibc_channel_query_grpc.QueryStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_channel(self, port_id: str, channel_id: str) -> Dict[str, Any]:
        request = ibc_channel_query.QueryChannelRequest(port_id=port_id, channel_id=channel_id)
        response = await self._execute_call(call=self._stub.Channel, request=request)

        return response

    async def fetch_channels(self, pagination: Optional[PaginationOption] = None) -> Dict[str, Any]:
        if pagination is None:
            pagination = PaginationOption()
        request = ibc_channel_query.QueryChannelsRequest(pagination=pagination.create_pagination_request())
        response = await self._execute_call(call=self._stub.Channels, request=request)

        return response

    async def fetch_connection_channels(
        self, connection: str, pagination: Optional[PaginationOption] = None
    ) -> Dict[str, Any]:
        if pagination is None:
            pagination = PaginationOption()
        request = ibc_channel_query.QueryConnectionChannelsRequest(
            connection=connection, pagination=pagination.create_pagination_request()
        )
        response = await self._execute_call(call=self._stub.ConnectionChannels, request=request)

        return response

    async def fetch_channel_client_state(
        self,
        port_id: str,
        channel_id: str,
    ) -> Dict[str, Any]:
        request = ibc_channel_query.QueryChannelClientStateRequest(
            port_id=port_id,
            channel_id=channel_id,
        )
        response = await self._execute_call(call=self._stub.ChannelClientState, request=request)

        return response

    async def fetch_channel_consensus_state(
        self,
        port_id: str,
        channel_id: str,
        revision_number: int,
        revision_height: int,
    ) -> Dict[str, Any]:
        request = ibc_channel_query.QueryChannelConsensusStateRequest(
            port_id=port_id,
            channel_id=channel_id,
            revision_number=revision_number,
            revision_height=revision_height,
        )
        response = await self._execute_call(call=self._stub.ChannelConsensusState, request=request)

        return response

    async def fetch_packet_commitment(
        self,
        port_id: str,
        channel_id: str,
        sequence: int,
    ) -> Dict[str, Any]:
        request = ibc_channel_query.QueryPacketCommitmentRequest(
            port_id=port_id,
            channel_id=channel_id,
            sequence=sequence,
        )
        response = await self._execute_call(call=self._stub.PacketCommitment, request=request)

        return response

    async def fetch_packet_commitments(
        self, port_id: str, channel_id: str, pagination: Optional[PaginationOption] = None
    ) -> Dict[str, Any]:
        if pagination is None:
            pagination = PaginationOption()
        request = ibc_channel_query.QueryPacketCommitmentsRequest(
            port_id=port_id, channel_id=channel_id, pagination=pagination.create_pagination_request()
        )
        response = await self._execute_call(call=self._stub.PacketCommitments, request=request)

        return response

    async def fetch_packet_receipt(self, port_id: str, channel_id: str, sequence: int) -> Dict[str, Any]:
        request = ibc_channel_query.QueryPacketReceiptRequest(port_id=port_id, channel_id=channel_id, sequence=sequence)
        response = await self._execute_call(call=self._stub.PacketReceipt, request=request)

        return response

    async def fetch_packet_acknowledgement(self, port_id: str, channel_id: str, sequence: int) -> Dict[str, Any]:
        request = ibc_channel_query.QueryPacketAcknowledgementRequest(
            port_id=port_id, channel_id=channel_id, sequence=sequence
        )
        response = await self._execute_call(call=self._stub.PacketAcknowledgement, request=request)

        return response

    async def fetch_packet_acknowledgements(
        self,
        port_id: str,
        channel_id: str,
        packet_commitment_sequences: Optional[List[int]] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        if pagination is None:
            pagination = PaginationOption()

        request = ibc_channel_query.QueryPacketAcknowledgementsRequest(
            port_id=port_id,
            channel_id=channel_id,
            packet_commitment_sequences=packet_commitment_sequences,
            pagination=pagination.create_pagination_request(),
        )
        response = await self._execute_call(call=self._stub.PacketAcknowledgements, request=request)

        return response

    async def fetch_unreceived_packets(
        self, port_id: str, channel_id: str, packet_commitment_sequences: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        request = ibc_channel_query.QueryUnreceivedPacketsRequest(
            port_id=port_id,
            channel_id=channel_id,
            packet_commitment_sequences=packet_commitment_sequences,
        )
        response = await self._execute_call(call=self._stub.UnreceivedPackets, request=request)

        return response

    async def fetch_unreceived_acks(
        self, port_id: str, channel_id: str, packet_ack_sequences: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        request = ibc_channel_query.QueryUnreceivedAcksRequest(
            port_id=port_id,
            channel_id=channel_id,
            packet_ack_sequences=packet_ack_sequences,
        )
        response = await self._execute_call(call=self._stub.UnreceivedAcks, request=request)

        return response

    async def fetch_next_sequence_receive(self, port_id: str, channel_id: str) -> Dict[str, Any]:
        request = ibc_channel_query.QueryNextSequenceReceiveRequest(
            port_id=port_id,
            channel_id=channel_id,
        )
        response = await self._execute_call(call=self._stub.NextSequenceReceive, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
