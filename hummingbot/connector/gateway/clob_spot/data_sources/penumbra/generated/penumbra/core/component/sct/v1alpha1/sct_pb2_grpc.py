# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.core.component.sct.v1alpha1 import (
    sct_pb2 as penumbra_dot_core_dot_component_dot_sct_dot_v1alpha1_dot_sct__pb2,
)


class QueryServiceStub(object):
    """Query operations for the SCT component.
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.TransactionByNote = channel.unary_unary(
                '/penumbra.core.component.sct.v1alpha1.QueryService/TransactionByNote',
                request_serializer=penumbra_dot_core_dot_component_dot_sct_dot_v1alpha1_dot_sct__pb2.TransactionByNoteRequest.SerializeToString,
                response_deserializer=penumbra_dot_core_dot_component_dot_sct_dot_v1alpha1_dot_sct__pb2.TransactionByNoteResponse.FromString,
                )


class QueryServiceServicer(object):
    """Query operations for the SCT component.
    """

    def TransactionByNote(self, request, context):
        """TODO: change to generic tx-by-commitment
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_QueryServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'TransactionByNote': grpc.unary_unary_rpc_method_handler(
                    servicer.TransactionByNote,
                    request_deserializer=penumbra_dot_core_dot_component_dot_sct_dot_v1alpha1_dot_sct__pb2.TransactionByNoteRequest.FromString,
                    response_serializer=penumbra_dot_core_dot_component_dot_sct_dot_v1alpha1_dot_sct__pb2.TransactionByNoteResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'penumbra.core.component.sct.v1alpha1.QueryService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


# This class is part of an EXPERIMENTAL API.
class QueryService(object):
    """Query operations for the SCT component.
    """

    @staticmethod
    def TransactionByNote(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/penumbra.core.component.sct.v1alpha1.QueryService/TransactionByNote',
            penumbra_dot_core_dot_component_dot_sct_dot_v1alpha1_dot_sct__pb2.TransactionByNoteRequest.SerializeToString,
            penumbra_dot_core_dot_component_dot_sct_dot_v1alpha1_dot_sct__pb2.TransactionByNoteResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)