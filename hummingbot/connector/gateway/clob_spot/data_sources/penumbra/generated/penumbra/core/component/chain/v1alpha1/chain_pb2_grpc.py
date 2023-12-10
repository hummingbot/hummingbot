# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.core.component.chain.v1alpha1 import (
    chain_pb2 as penumbra_dot_core_dot_component_dot_chain_dot_v1alpha1_dot_chain__pb2,
)


class QueryServiceStub(object):
    """Query operations for the chain component.
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.EpochByHeight = channel.unary_unary(
                '/penumbra.core.component.chain.v1alpha1.QueryService/EpochByHeight',
                request_serializer=penumbra_dot_core_dot_component_dot_chain_dot_v1alpha1_dot_chain__pb2.EpochByHeightRequest.SerializeToString,
                response_deserializer=penumbra_dot_core_dot_component_dot_chain_dot_v1alpha1_dot_chain__pb2.EpochByHeightResponse.FromString,
                )


class QueryServiceServicer(object):
    """Query operations for the chain component.
    """

    def EpochByHeight(self, request, context):
        """TODO: move to SCT cf sct/src/component/view.rs:9 "make epoch management the responsibility of this component"
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_QueryServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'EpochByHeight': grpc.unary_unary_rpc_method_handler(
                    servicer.EpochByHeight,
                    request_deserializer=penumbra_dot_core_dot_component_dot_chain_dot_v1alpha1_dot_chain__pb2.EpochByHeightRequest.FromString,
                    response_serializer=penumbra_dot_core_dot_component_dot_chain_dot_v1alpha1_dot_chain__pb2.EpochByHeightResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'penumbra.core.component.chain.v1alpha1.QueryService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


# This class is part of an EXPERIMENTAL API.
class QueryService(object):
    """Query operations for the chain component.
    """

    @staticmethod
    def EpochByHeight(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/penumbra.core.component.chain.v1alpha1.QueryService/EpochByHeight',
            penumbra_dot_core_dot_component_dot_chain_dot_v1alpha1_dot_chain__pb2.EpochByHeightRequest.SerializeToString,
            penumbra_dot_core_dot_component_dot_chain_dot_v1alpha1_dot_chain__pb2.EpochByHeightResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)