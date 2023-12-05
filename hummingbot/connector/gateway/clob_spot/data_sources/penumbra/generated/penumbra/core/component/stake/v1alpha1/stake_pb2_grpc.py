# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.core.component.stake.v1alpha1 import (
    stake_pb2 as penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2,
)


class QueryServiceStub(object):
    """Query operations for the staking component.
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.ValidatorInfo = channel.unary_stream(
                '/penumbra.core.component.stake.v1alpha1.QueryService/ValidatorInfo',
                request_serializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorInfoRequest.SerializeToString,
                response_deserializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorInfoResponse.FromString,
                )
        self.ValidatorStatus = channel.unary_unary(
                '/penumbra.core.component.stake.v1alpha1.QueryService/ValidatorStatus',
                request_serializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorStatusRequest.SerializeToString,
                response_deserializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorStatusResponse.FromString,
                )
        self.ValidatorPenalty = channel.unary_unary(
                '/penumbra.core.component.stake.v1alpha1.QueryService/ValidatorPenalty',
                request_serializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorPenaltyRequest.SerializeToString,
                response_deserializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorPenaltyResponse.FromString,
                )
        self.CurrentValidatorRate = channel.unary_unary(
                '/penumbra.core.component.stake.v1alpha1.QueryService/CurrentValidatorRate',
                request_serializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.CurrentValidatorRateRequest.SerializeToString,
                response_deserializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.CurrentValidatorRateResponse.FromString,
                )
        self.NextValidatorRate = channel.unary_unary(
                '/penumbra.core.component.stake.v1alpha1.QueryService/NextValidatorRate',
                request_serializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.NextValidatorRateRequest.SerializeToString,
                response_deserializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.NextValidatorRateResponse.FromString,
                )


class QueryServiceServicer(object):
    """Query operations for the staking component.
    """

    def ValidatorInfo(self, request, context):
        """Queries the current validator set, with filtering.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ValidatorStatus(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ValidatorPenalty(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def CurrentValidatorRate(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def NextValidatorRate(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_QueryServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'ValidatorInfo': grpc.unary_stream_rpc_method_handler(
                    servicer.ValidatorInfo,
                    request_deserializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorInfoRequest.FromString,
                    response_serializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorInfoResponse.SerializeToString,
            ),
            'ValidatorStatus': grpc.unary_unary_rpc_method_handler(
                    servicer.ValidatorStatus,
                    request_deserializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorStatusRequest.FromString,
                    response_serializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorStatusResponse.SerializeToString,
            ),
            'ValidatorPenalty': grpc.unary_unary_rpc_method_handler(
                    servicer.ValidatorPenalty,
                    request_deserializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorPenaltyRequest.FromString,
                    response_serializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorPenaltyResponse.SerializeToString,
            ),
            'CurrentValidatorRate': grpc.unary_unary_rpc_method_handler(
                    servicer.CurrentValidatorRate,
                    request_deserializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.CurrentValidatorRateRequest.FromString,
                    response_serializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.CurrentValidatorRateResponse.SerializeToString,
            ),
            'NextValidatorRate': grpc.unary_unary_rpc_method_handler(
                    servicer.NextValidatorRate,
                    request_deserializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.NextValidatorRateRequest.FromString,
                    response_serializer=penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.NextValidatorRateResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'penumbra.core.component.stake.v1alpha1.QueryService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


# This class is part of an EXPERIMENTAL API.
class QueryService(object):
    """Query operations for the staking component.
    """

    @staticmethod
    def ValidatorInfo(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_stream(request, target, '/penumbra.core.component.stake.v1alpha1.QueryService/ValidatorInfo',
            penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorInfoRequest.SerializeToString,
            penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorInfoResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def ValidatorStatus(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/penumbra.core.component.stake.v1alpha1.QueryService/ValidatorStatus',
            penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorStatusRequest.SerializeToString,
            penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorStatusResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def ValidatorPenalty(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/penumbra.core.component.stake.v1alpha1.QueryService/ValidatorPenalty',
            penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorPenaltyRequest.SerializeToString,
            penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.ValidatorPenaltyResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def CurrentValidatorRate(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/penumbra.core.component.stake.v1alpha1.QueryService/CurrentValidatorRate',
            penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.CurrentValidatorRateRequest.SerializeToString,
            penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.CurrentValidatorRateResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def NextValidatorRate(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/penumbra.core.component.stake.v1alpha1.QueryService/NextValidatorRate',
            penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.NextValidatorRateRequest.SerializeToString,
            penumbra_dot_core_dot_component_dot_stake_dot_v1alpha1_dot_stake__pb2.NextValidatorRateResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
