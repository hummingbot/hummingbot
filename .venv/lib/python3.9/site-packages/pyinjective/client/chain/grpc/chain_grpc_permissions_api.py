from typing import Any, Callable, Dict

from grpc.aio import Channel

from pyinjective.core.network import CookieAssistant
from pyinjective.proto.injective.permissions.v1beta1 import (
    query_pb2 as permissions_query_pb,
    query_pb2_grpc as permissions_query_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class ChainGrpcPermissionsApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = permissions_query_grpc.QueryStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_module_params(self) -> Dict[str, Any]:
        request = permissions_query_pb.QueryParamsRequest()
        response = await self._execute_call(call=self._stub.Params, request=request)

        return response

    async def fetch_namespace_denoms(self) -> Dict[str, Any]:
        request = permissions_query_pb.QueryNamespaceDenomsRequest()
        response = await self._execute_call(call=self._stub.NamespaceDenoms, request=request)

        return response

    async def fetch_namespaces(self) -> Dict[str, Any]:
        request = permissions_query_pb.QueryNamespacesRequest()
        response = await self._execute_call(call=self._stub.Namespaces, request=request)

        return response

    async def fetch_namespace(self, denom: str) -> Dict[str, Any]:
        request = permissions_query_pb.QueryNamespaceRequest(denom=denom)
        response = await self._execute_call(call=self._stub.Namespace, request=request)

        return response

    async def fetch_roles_by_actor(self, denom: str, actor: str) -> Dict[str, Any]:
        request = permissions_query_pb.QueryRolesByActorRequest(denom=denom, actor=actor)
        response = await self._execute_call(call=self._stub.RolesByActor, request=request)

        return response

    async def fetch_actors_by_role(self, denom: str, role: str) -> Dict[str, Any]:
        request = permissions_query_pb.QueryActorsByRoleRequest(denom=denom, role=role)
        response = await self._execute_call(call=self._stub.ActorsByRole, request=request)

        return response

    async def fetch_role_managers(self, denom: str) -> Dict[str, Any]:
        request = permissions_query_pb.QueryRoleManagersRequest(denom=denom)
        response = await self._execute_call(call=self._stub.RoleManagers, request=request)

        return response

    async def fetch_role_manager(self, denom: str, manager: str) -> Dict[str, Any]:
        request = permissions_query_pb.QueryRoleManagerRequest(denom=denom, manager=manager)
        response = await self._execute_call(call=self._stub.RoleManager, request=request)

        return response

    async def fetch_policy_statuses(self, denom: str) -> Dict[str, Any]:
        request = permissions_query_pb.QueryPolicyStatusesRequest(denom=denom)
        response = await self._execute_call(call=self._stub.PolicyStatuses, request=request)

        return response

    async def fetch_policy_manager_capabilities(self, denom: str) -> Dict[str, Any]:
        request = permissions_query_pb.QueryPolicyManagerCapabilitiesRequest(denom=denom)
        response = await self._execute_call(call=self._stub.PolicyManagerCapabilities, request=request)

        return response

    async def fetch_vouchers(self, denom: str) -> Dict[str, Any]:
        request = permissions_query_pb.QueryVouchersRequest(denom=denom)
        response = await self._execute_call(call=self._stub.Vouchers, request=request)

        return response

    async def fetch_voucher(self, denom: str, address: str) -> Dict[str, Any]:
        request = permissions_query_pb.QueryVoucherRequest(denom=denom, address=address)
        response = await self._execute_call(call=self._stub.Voucher, request=request)

        return response

    async def fetch_permissions_module_state(self) -> Dict[str, Any]:
        request = permissions_query_pb.QueryModuleStateRequest()
        response = await self._execute_call(call=self._stub.PermissionsModuleState, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
