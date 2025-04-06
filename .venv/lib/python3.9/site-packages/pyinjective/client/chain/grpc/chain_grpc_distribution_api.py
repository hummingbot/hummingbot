from typing import Any, Callable, Dict, Optional

from grpc.aio import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.cosmos.distribution.v1beta1 import (
    query_pb2 as distribution_query_pb,
    query_pb2_grpc as distribution_query_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class ChainGrpcDistributionApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = distribution_query_grpc.QueryStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_module_params(self) -> Dict[str, Any]:
        request = distribution_query_pb.QueryParamsRequest()
        response = await self._execute_call(call=self._stub.Params, request=request)

        return response

    async def fetch_validator_distribution_info(self, validator_address: str) -> Dict[str, Any]:
        request = distribution_query_pb.QueryValidatorDistributionInfoRequest(validator_address=validator_address)
        response = await self._execute_call(call=self._stub.ValidatorDistributionInfo, request=request)

        return response

    async def fetch_validator_outstanding_rewards(self, validator_address: str) -> Dict[str, Any]:
        request = distribution_query_pb.QueryValidatorOutstandingRewardsRequest(validator_address=validator_address)
        response = await self._execute_call(call=self._stub.ValidatorOutstandingRewards, request=request)

        return response

    async def fetch_validator_commission(self, validator_address: str) -> Dict[str, Any]:
        request = distribution_query_pb.QueryValidatorCommissionRequest(validator_address=validator_address)
        response = await self._execute_call(call=self._stub.ValidatorCommission, request=request)

        return response

    async def fetch_validator_slashes(
        self,
        validator_address: str,
        starting_height: Optional[int] = None,
        ending_height: Optional[int] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = distribution_query_pb.QueryValidatorSlashesRequest(
            validator_address=validator_address,
            starting_height=starting_height,
            ending_height=ending_height,
            pagination=pagination_request,
        )
        response = await self._execute_call(call=self._stub.ValidatorSlashes, request=request)

        return response

    async def fetch_delegation_rewards(
        self,
        delegator_address: str,
        validator_address: str,
    ) -> Dict[str, Any]:
        request = distribution_query_pb.QueryDelegationRewardsRequest(
            delegator_address=delegator_address,
            validator_address=validator_address,
        )
        response = await self._execute_call(call=self._stub.DelegationRewards, request=request)

        return response

    async def fetch_delegation_total_rewards(
        self,
        delegator_address: str,
    ) -> Dict[str, Any]:
        request = distribution_query_pb.QueryDelegationTotalRewardsRequest(
            delegator_address=delegator_address,
        )
        response = await self._execute_call(call=self._stub.DelegationTotalRewards, request=request)

        return response

    async def fetch_delegator_validators(self, delegator_address: str) -> Dict[str, Any]:
        request = distribution_query_pb.QueryDelegatorValidatorsRequest(
            delegator_address=delegator_address,
        )
        response = await self._execute_call(call=self._stub.DelegatorValidators, request=request)

        return response

    async def fetch_delegator_withdraw_address(self, delegator_address: str) -> Dict[str, Any]:
        request = distribution_query_pb.QueryDelegatorWithdrawAddressRequest(
            delegator_address=delegator_address,
        )
        response = await self._execute_call(call=self._stub.DelegatorWithdrawAddress, request=request)

        return response

    async def fetch_community_pool(self) -> Dict[str, Any]:
        request = distribution_query_pb.QueryCommunityPoolRequest()
        response = await self._execute_call(call=self._stub.CommunityPool, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
