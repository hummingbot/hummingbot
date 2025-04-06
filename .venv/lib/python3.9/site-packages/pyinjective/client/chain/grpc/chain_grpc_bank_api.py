from typing import Any, Callable, Dict, List, Optional

from grpc.aio import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.cosmos.bank.v1beta1 import query_pb2 as bank_query_pb, query_pb2_grpc as bank_query_grpc
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class ChainGrpcBankApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = bank_query_grpc.QueryStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_module_params(self) -> Dict[str, Any]:
        request = bank_query_pb.QueryParamsRequest()
        response = await self._execute_call(call=self._stub.Params, request=request)

        return response

    async def fetch_balance(self, account_address: str, denom: str) -> Dict[str, Any]:
        request = bank_query_pb.QueryBalanceRequest(address=account_address, denom=denom)
        response = await self._execute_call(call=self._stub.Balance, request=request)

        return response

    async def fetch_balances(self, account_address: str) -> Dict[str, Any]:
        request = bank_query_pb.QueryAllBalancesRequest(address=account_address)
        response = await self._execute_call(call=self._stub.AllBalances, request=request)

        return response

    async def fetch_spendable_balances(
        self,
        account_address: str,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = bank_query_pb.QuerySpendableBalancesRequest(
            address=account_address,
            pagination=pagination_request,
        )
        response = await self._execute_call(call=self._stub.SpendableBalances, request=request)

        return response

    async def fetch_spendable_balances_by_denom(
        self,
        account_address: str,
        denom: str,
    ) -> Dict[str, Any]:
        request = bank_query_pb.QuerySpendableBalanceByDenomRequest(
            address=account_address,
            denom=denom,
        )
        response = await self._execute_call(call=self._stub.SpendableBalanceByDenom, request=request)

        return response

    async def fetch_total_supply(self, pagination: Optional[PaginationOption] = None) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = bank_query_pb.QueryTotalSupplyRequest(pagination=pagination_request)
        response = await self._execute_call(call=self._stub.TotalSupply, request=request)

        return response

    async def fetch_supply_of(self, denom: str) -> Dict[str, Any]:
        request = bank_query_pb.QuerySupplyOfRequest(denom=denom)
        response = await self._execute_call(call=self._stub.SupplyOf, request=request)

        return response

    async def fetch_denom_metadata(self, denom: str) -> Dict[str, Any]:
        request = bank_query_pb.QueryDenomMetadataRequest(denom=denom)
        response = await self._execute_call(call=self._stub.DenomMetadata, request=request)

        return response

    async def fetch_denoms_metadata(self, pagination: Optional[PaginationOption] = None) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = bank_query_pb.QueryDenomsMetadataRequest(pagination=pagination_request)
        response = await self._execute_call(call=self._stub.DenomsMetadata, request=request)

        return response

    async def fetch_denom_owners(self, denom: str, pagination: Optional[PaginationOption] = None) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = bank_query_pb.QueryDenomOwnersRequest(denom=denom, pagination=pagination_request)
        response = await self._execute_call(call=self._stub.DenomOwners, request=request)

        return response

    async def fetch_send_enabled(
        self,
        denoms: Optional[List[str]] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = bank_query_pb.QuerySendEnabledRequest(denoms=denoms, pagination=pagination_request)
        response = await self._execute_call(call=self._stub.SendEnabled, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
