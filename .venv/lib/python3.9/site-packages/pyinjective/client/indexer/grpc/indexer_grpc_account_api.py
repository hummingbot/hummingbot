from typing import Any, Callable, Dict, List, Optional

from grpc.aio import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.exchange import (
    injective_accounts_rpc_pb2 as exchange_accounts_pb,
    injective_accounts_rpc_pb2_grpc as exchange_accounts_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class IndexerGrpcAccountApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = self._stub = exchange_accounts_grpc.InjectiveAccountsRPCStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_portfolio(self, account_address: str) -> Dict[str, Any]:
        request = exchange_accounts_pb.PortfolioRequest(account_address=account_address)
        response = await self._execute_call(call=self._stub.Portfolio, request=request)

        return response

    async def fetch_order_states(
        self,
        spot_order_hashes: Optional[List[str]] = None,
        derivative_order_hashes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        spot_order_hashes = spot_order_hashes or []
        derivative_order_hashes = derivative_order_hashes or []

        request = exchange_accounts_pb.OrderStatesRequest(
            spot_order_hashes=spot_order_hashes, derivative_order_hashes=derivative_order_hashes
        )
        response = await self._execute_call(call=self._stub.OrderStates, request=request)

        return response

    async def fetch_subaccounts_list(self, address: str) -> Dict[str, Any]:
        request = exchange_accounts_pb.SubaccountsListRequest(account_address=address)
        response = await self._execute_call(call=self._stub.SubaccountsList, request=request)

        return response

    async def fetch_subaccount_balances_list(
        self, subaccount_id: str, denoms: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        request = exchange_accounts_pb.SubaccountBalancesListRequest(
            subaccount_id=subaccount_id,
            denoms=denoms,
        )
        response = await self._execute_call(call=self._stub.SubaccountBalancesList, request=request)

        return response

    async def fetch_subaccount_balance(self, subaccount_id: str, denom: str) -> Dict[str, Any]:
        request = exchange_accounts_pb.SubaccountBalanceEndpointRequest(
            subaccount_id=subaccount_id,
            denom=denom,
        )
        response = await self._execute_call(call=self._stub.SubaccountBalanceEndpoint, request=request)

        return response

    async def fetch_subaccount_history(
        self,
        subaccount_id: str,
        denom: Optional[str] = None,
        transfer_types: Optional[List[str]] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_accounts_pb.SubaccountHistoryRequest(
            subaccount_id=subaccount_id,
            denom=denom,
            transfer_types=transfer_types,
            skip=pagination.skip,
            limit=pagination.limit,
            end_time=pagination.end_time,
        )
        response = await self._execute_call(call=self._stub.SubaccountHistory, request=request)

        return response

    async def fetch_subaccount_order_summary(
        self,
        subaccount_id: str,
        market_id: Optional[str] = None,
        order_direction: Optional[str] = None,
    ) -> Dict[str, Any]:
        request = exchange_accounts_pb.SubaccountOrderSummaryRequest(
            subaccount_id=subaccount_id,
            market_id=market_id,
            order_direction=order_direction,
        )
        response = await self._execute_call(call=self._stub.SubaccountOrderSummary, request=request)

        return response

    async def fetch_rewards(self, account_address: Optional[str] = None, epoch: Optional[int] = None) -> Dict[str, Any]:
        request = exchange_accounts_pb.RewardsRequest(account_address=account_address, epoch=epoch)
        response = await self._execute_call(call=self._stub.Rewards, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
