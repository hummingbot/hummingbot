from typing import Any, Callable, Dict, Optional

from grpc.aio import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.cosmwasm.wasm.v1 import query_pb2 as wasm_query_pb, query_pb2_grpc as wasm_query_grpc
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class ChainGrpcWasmApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = wasm_query_grpc.QueryStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_module_params(self) -> Dict[str, Any]:
        request = wasm_query_pb.QueryParamsRequest()
        response = await self._execute_call(call=self._stub.Params, request=request)

        return response

    async def fetch_contract_info(self, address: str) -> Dict[str, Any]:
        request = wasm_query_pb.QueryContractInfoRequest(address=address)
        response = await self._execute_call(call=self._stub.ContractInfo, request=request)

        return response

    async def fetch_contract_history(
        self,
        address: str,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = wasm_query_pb.QueryContractHistoryRequest(
            address=address,
            pagination=pagination_request,
        )
        response = await self._execute_call(call=self._stub.ContractHistory, request=request)

        return response

    async def fetch_contracts_by_code(
        self,
        code_id: int,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = wasm_query_pb.QueryContractsByCodeRequest(
            code_id=code_id,
            pagination=pagination_request,
        )
        response = await self._execute_call(call=self._stub.ContractsByCode, request=request)

        return response

    async def fetch_all_contracts_state(
        self,
        address: str,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = wasm_query_pb.QueryAllContractStateRequest(
            address=address,
            pagination=pagination_request,
        )
        response = await self._execute_call(call=self._stub.AllContractState, request=request)

        return response

    async def fetch_raw_contract_state(self, address: str, query_data: str) -> Dict[str, Any]:
        request = wasm_query_pb.QueryRawContractStateRequest(
            address=address,
            query_data=query_data.encode(),
        )
        response = await self._execute_call(call=self._stub.RawContractState, request=request)

        return response

    async def fetch_smart_contract_state(self, address: str, query_data: str) -> Dict[str, Any]:
        request = wasm_query_pb.QuerySmartContractStateRequest(
            address=address,
            query_data=query_data.encode(),
        )
        response = await self._execute_call(call=self._stub.SmartContractState, request=request)

        return response

    async def fetch_code(self, code_id: int) -> Dict[str, Any]:
        request = wasm_query_pb.QueryCodeRequest(code_id=code_id)
        response = await self._execute_call(call=self._stub.Code, request=request)

        return response

    async def fetch_codes(
        self,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = wasm_query_pb.QueryCodesRequest(
            pagination=pagination_request,
        )
        response = await self._execute_call(call=self._stub.Codes, request=request)

        return response

    async def fetch_pinned_codes(
        self,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = wasm_query_pb.QueryPinnedCodesRequest(
            pagination=pagination_request,
        )
        response = await self._execute_call(call=self._stub.PinnedCodes, request=request)

        return response

    async def fetch_contracts_by_creator(
        self,
        creator_address: str,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination_request = None
        if pagination is not None:
            pagination_request = pagination.create_pagination_request()
        request = wasm_query_pb.QueryContractsByCreatorRequest(
            creator_address=creator_address,
            pagination=pagination_request,
        )
        response = await self._execute_call(call=self._stub.ContractsByCreator, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
